"""The console's Contact page: where it replies and downloads, its limits, and its words (console/contact.py,
evidence/contact.py). The inbox itself is the newsletters Worker's (cloudflare/newsletters/)."""
from evidence.console_settings import CONTACT_INBOX_URL

REPLY_URL = f"{CONTACT_INBOX_URL}/reply"                     # POST {thread, text}, with the inbox token
ATTACHMENT_URL = f"{CONTACT_INBOX_URL}/attachments/{{id}}"   # GET, with the inbox token; only once the file is clean
REPLY_CHARACTERS = 4000          # as the Worker's CONTACT_TEXT_CHARACTERS
REPLY_TIMEOUT_SECONDS = 20
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOADS_KEPT = 20              # clean files kept in the console's memory, so opening a thread again reads none twice
SCAN_EVERY = "every 3 hours"  # as .github/workflows/contact-scan.yml runs: about 240 Actions minutes a month,
                              # where every 30 minutes would take 1,440 of a private repo's 2,000 free
SCAN_TOKEN_ENV = "CONTACT_SCAN_TOKEN"   # scripts/contact_scan.py: the Worker's secret of that name, a GitHub Actions secret

NO_SUBJECT = "(no subject)"
NO_SENDER = "no sender"
NO_TEXT = "(no text)"
FROM_FORM = "sent from the dashboard form; address not verified"
NOT_VERIFIED = "address not verified"
FROM_US = "Sent by the team to {to}"
FROM_THEM = "From {sender}"

THREADS = "Threads"
THREADS_NOTE = "{count}, the latest first"
THREAD_COLUMNS = ["Correspondent", "Subject", "Last message", "Messages"]
OPEN_THREAD = "Open a thread"
THREAD_NOTE = "{count} messages, the oldest first; times in UTC"
EMPTY = "No message has arrived yet."

PENDING = f"being scanned (checked {SCAN_EVERY})"
CLEAN = "scanned: no virus found; download it below"
INFECTED = "removed: virus found ({signature})"
MISSING = "missing from the inbox store"
DOWNLOAD = "Download {name} ({size})"
DOWNLOAD_FAILED = "{name} could not be read from the inbox now. Read the inbox again in a few minutes."

REPLY_LABEL = "Reply to {address}"
REPLY_HELP = "Plain text. It goes only to this thread's correspondent, from contact@opengnss.org."
SEND = "Send reply"
SENT = "Sent to {address}."
NOT_SENT = "Not sent: {why}"
REPLY_EMPTY = "the reply is empty."
REPLY_TOO_LONG = "the reply is {length} characters long; the most is {limit}."
REPLY_REFUSED = "the inbox refused it ({problem})."
REPLY_TOKEN = ("the inbox refused the console's token: [admin] contact_read_token must be the same as the Worker's "
               "secret CONTACT_READ_TOKEN.")
REPLY_NO_ANSWER = ("The inbox did not answer, so the reply may or may not have been sent. Read the inbox again and look "
                   "for it in the thread before sending it again.")
