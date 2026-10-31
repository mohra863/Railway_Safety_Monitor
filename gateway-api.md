# The Hafnia gateway API

The gateway on your machine has a REST API: ask Hafnia VLM about a clip, read the answers, and manage prompts and
gateway rules. It is the same API that Smart Client and the gateway page use.

## Before you start

- **Address:** `https://localhost:15443`. Your code must run on the machine.
- **From your laptop:** the gateway is not reachable. Laptop code reaches Hafnia through XProtect instead: see the
  `xprotect-hackathon` skill, "Working from your laptop", and `webhooks.md`.
- **Tools:** Python and the .NET SDK are not installed on the machine. Install Python 3.11 or later from python.org
  (it adds the `py` command) or the .NET 8 SDK first.
- **Certificate:** the gateway's certificate is self-signed, so your HTTP client must accept it. The examples below
  turn certificate checks off for one client: use that client only for the gateway.
- **Windows PowerShell 5.1:** `Invoke-RestMethod` and `Invoke-WebRequest` cannot connect to the gateway. Use Python,
  C# or `curl.exe`.
- **Web pages:** a page in a browser cannot call the gateway directly; the gateway does not allow it. Call the
  gateway from your own server-side code on the machine, and serve the result to your page.
- **Try it by hand:** open `https://localhost:15443/api/swagger/` in Edge. Use *Sessions*, *Login* to log in, copy
  the `Id` from the answer, click **Authorize** and paste it. Every call you then make there is real.
- **Cost:** a summary that completes costs 1 of your 500 requests a day; one that fails before it reaches Hafnia
  VLM costs nothing. All other calls are free.

## Log in once, then send the session with every call

`POST /api/Sessions/Login` with the gateway's user and password:

```json
{ "Name": "administrator", "Password": "<your Windows password>" }
```

The answer holds the session in `Id`. Send it as the header `X-Session-Id` on every other call.

- A session lasts 8 hours from login, however much you use it. A gateway restart ends all sessions.
- An expired or wrong session gives 401: log in again.
- The machine allows 10 logins a minute in total, including logins on the gateway page. More give 429 until the
  minute is over. Log in once and reuse the session.
- Keep the password out of your code: read it from an environment variable, or let your code ask for it when it runs,
  as the examples do.

## Endpoints

| Call | What it does |
|---|---|
| `POST /api/Sessions/Login` | Log in (no session needed); see above |
| `POST /api/Sessions/Logout` | End the session; body `{"Id": "<session>"}` |
| `GET /api/System/Information` | Gateway version, counts, and today's allowance (no session needed) |
| `GET /api/Models` | The AI models: `Id`, `Name`, `Description`, `IsDefault` |
| `GET /api/Prompts` | The prompts: `{"TotalCount", "PageContent": [{"Id", "Title", "Text"}]}`. Optional `SearchString` (part of a title), `Limit`, `Offset` |
| `GET /api/Prompts/{id}` | One prompt. An unknown id gives status 204 and an empty body. |
| `POST /api/Prompts` | Create a prompt: `{"Title", "Text"}`; the answer is the prompt with its new `Id` |
| `PUT /api/Prompts/{id}` | Change a prompt: `{"Title", "Text"}` |
| `DELETE /api/Prompts/{id}` | Delete a prompt |
| `POST /api/Summaries` | Ask Hafnia VLM about a clip (below) |
| `GET /api/Summaries/{id}` | One request and its answer; 404 if unknown |
| `GET /api/Summaries` | List requests and answers (below) |
| `GET /api/Rules`, `POST /api/Rules`, `PUT /api/Rules/{id}`, `DELETE /api/Rules/{id}` | Gateway rules (below) |
| `GET /api/Rules/Actions/TriggerAnalyticsEvent/Options` | The analytics event names that XProtect has |

Answers are JSON with PascalCase names; fields without a value are left out. Leave the gateway's settings alone
through the API: a mistake there can disconnect the gateway from Hafnia VLM or XProtect.

## Ask about a clip

`POST /api/Summaries`:

```json
{
  "Prompt": "Describe what happens in this video.",
  "VideoUris": ["xprotect://localhost/cameras/<camera id>?StartTime=2026-10-07T10:00:00Z&EndTime=2026-10-07T10:00:30Z"]
}
```

| Field | Meaning |
|---|---|
| `Prompt` | Required: the text Hafnia VLM receives |
| `VideoUris` | Required: exactly one clip, as `xprotect://localhost/cameras/<camera id>?StartTime=<UTC>&EndTime=<UTC>`. With none, or more than one, the gateway still accepts the request, then marks it *Failed*. |
| `PromptId` | Optional: the `Id` of a saved prompt. Only then do gateway rules for that prompt check the answer. The gateway does not look the text up: send the prompt's text in `Prompt` as well. |
| `AiModelId` | Optional: an `Id` from `/api/Models`; without it, the default model |

- Use times from the last 24 hours: older recordings are gone.
- Write the times in UTC with `Z`, as in the example. A time without `Z` is read as the machine's local time. Never
  write an offset such as `+02:00`: in the address, `+` is read as a space.
- Camera IDs come from XProtect: the tour script in the `xprotect-hackathon` skill prints them, or in PowerShell
  `Connect-Vms -ServerAddress 'http://localhost' -AcceptEula; Get-VmsCamera | Select-Object Name, Id`. IDs change
  when a machine is rebuilt, so look cameras up by name in your code.
- Prompt IDs change when prompts are imported: find a prompt's `Id` with `GET /api/Prompts?SearchString=<title>` and
  pick the one whose `Title` matches exactly.
- The clip must be recorded: pick a time within the last 24 hours. A clip that ends in the future waits until that
  time has passed.
- The answer is the new request, with its `Id` and `Progress`. Hafnia's work continues in the background.

## Wait for the answer

Read `GET /api/Summaries/{id}` every few seconds until `Progress` is `Completed` or `Failed`. The gateway gives the
export 60 seconds and Hafnia VLM 300 seconds, so stop waiting after 10 minutes.

| `Progress` | Meaning |
|---|---|
| `NotStarted` | Accepted |
| `FetchingVideo` | Exporting the clip from XProtect |
| `TransferringAssets` | Uploading the clip to Hafnia VLM |
| `RequestingSummary` | Waiting for Hafnia VLM's answer |
| `Completed` | The answer is in `Response` |
| `Failed` | The reason is in `LastError` |

A request has these fields: `Id`, `CreationTimeUtc`, `LastUpdatedTimeUtc`, `Request` (what was sent), `Source`
(`Trigger` is `Manual` or `Webhook`; webhooks add `TriggerName` and `SourceName`), `Progress`, `Response`,
`LastError`. Times may come back with `Z` or with an offset such as `+02:00`: read them as times with an offset.

### Python

`C:\HackathonKit\hafnia-vlm\scripts\ask_hafnia.py` is a complete Python example: it logs in, looks a saved prompt
up by title, asks, waits up to 10 minutes, and prints the answer.
`py C:\HackathonKit\hafnia-vlm\scripts\ask_hafnia.py --help` shows how to run it.

### C#, .NET 8

```csharp
using System.Net.Http.Json;
using System.Text.Json;

// Certificate checks off for this client: use it only for the gateway (its certificate is self-signed).
var handler = new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = HttpClientHandler.DangerousAcceptAnyServerCertificateValidator
};
using var gateway = new HttpClient(handler) { BaseAddress = new Uri("https://localhost:15443"), Timeout = TimeSpan.FromSeconds(60) };

var password = Environment.GetEnvironmentVariable("HAFNIA_GW_PASSWORD") ?? throw new InvalidOperationException("Set HAFNIA_GW_PASSWORD");
var login = await gateway.PostAsJsonAsync("/api/Sessions/Login", new { Name = "administrator", Password = password });
login.EnsureSuccessStatusCode();
var session = (await login.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("Id").GetString();
gateway.DefaultRequestHeaders.Add("X-Session-Id", session);

Console.Write("Camera ID: ");
var cameraId = Console.ReadLine();
var end = DateTime.UtcNow.AddSeconds(-5);
var start = end.AddSeconds(-30);
var created = await gateway.PostAsJsonAsync("/api/Summaries", new
{
    Prompt = "Describe what happens in this video.",
    VideoUris = new[] { $"xprotect://localhost/cameras/{cameraId}?StartTime={start:o}&EndTime={end:o}" }
});
created.EnsureSuccessStatusCode();
var summary = await created.Content.ReadFromJsonAsync<JsonElement>();
var id = summary.GetProperty("Id").GetString();

var progress = summary.GetProperty("Progress").GetString();
var deadline = DateTime.UtcNow.AddMinutes(10);
while (progress is not ("Completed" or "Failed") && DateTime.UtcNow < deadline)
{
    await Task.Delay(TimeSpan.FromSeconds(3));
    summary = await gateway.GetFromJsonAsync<JsonElement>($"/api/Summaries/{id}");
    progress = summary.GetProperty("Progress").GetString();
    Console.WriteLine(progress);
}
Console.WriteLine(progress switch
{
    "Completed" => summary.GetProperty("Response").GetString(),
    "Failed" => summary.GetProperty("LastError").GetString(),
    _ => "Still running after 10 minutes: see History in Smart Client"
});
```

## List requests and answers

`GET /api/Summaries` returns `{"TotalCount", "PageContent": [...]}`, newest first. Always pass `Limit`: without it
you get every request the gateway has kept. Repeat a parameter for several values, for example
`Progresses=Completed&Progresses=Failed`:

| Parameter | Values |
|---|---|
| `SearchString` | Text to find in the answers |
| `SearchProperties` | Where to search: `Response` (default), `TriggerName`, `SourceName` |
| `Triggers` | `Manual`, `Webhook` |
| `Progresses` | `NotStarted`, `FetchingVideo`, `TransferringAssets`, `RequestingSummary`, `Completed`, `Failed` |
| `CreationTimeUtcStart`, `CreationTimeUtcEnd` | UTC times with `Z`; the start is included, the end is not |
| `CreationTimeUtcOrderBy` | `Ascending` or `Descending` (default) |
| `Limit`, `Offset` | Paging |

To keep only one camera's requests, check `Request.VideoUris` in your code. There is no way to delete a request;
the gateway keeps requests 30 days by default, failed ones 1 day.

## Gateway rules through the API

Useful to recreate your rules on a fresh machine. Find the prompt's `Id` by title first (above), then
`POST /api/Rules`:

```json
{
  "Name": "Vandalism",
  "Description": "Raise an alarm when Hafnia confirms vandalism",
  "PromptId": "<saved prompt id>",
  "Triggers": [
    { "TriggerText": "VANDALISM_CONFIRMED", "RuleActionId": "TriggerAnalyticsEvent", "RuleActionData": "Hafnia vandalism confirmed" }
  ]
}
```

`RuleActionData` is the analytics event's name in XProtect. To change a rule, `PUT /api/Rules/{id}` with the whole
rule, including its `Id` in the body. How rules match answers: `gateway-rules.md`.

## When a call fails

| Status | Meaning |
|---|---|
| 400 | The body is not valid; the answer names the field |
| 401 | From *Login*: wrong user or password. From any other call: no session, or it expired or ended with a gateway restart: log in again |
| 404 | No request with that `Id` |
| 429 | Too many logins in the last minute: wait until the minute is over, and reuse sessions |
| 500 | The gateway failed: search its log files in `C:\ProgramData\VideoOS\Hafnia.Vlm.Gateway\logs` |
