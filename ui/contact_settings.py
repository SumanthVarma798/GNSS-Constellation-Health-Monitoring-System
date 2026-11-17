"""The contact form's words, limits and names (ui/contact.py).

A message goes to the newsletters Worker's POST /contact (cloudflare/newsletters) and lands in the private contact
inbox the console reads (console/contact.py). It is never published.
"""
from evidence.console_settings import CONTACT_ADDRESS

# Where to send, from the dashboard's environment or else its secrets ([contact] url and token). Either missing:
# no form is drawn. The token is the Worker's CONTACT_WRITE_TOKEN, which can add a message but never read one.
URL_ENV, TOKEN_ENV = "CONTACT_FORM_URL", "CONTACT_FORM_TOKEN"
SECRETS_SECTION, URL_KEY, TOKEN_KEY = "contact", "url", "token"
SEND_TIMEOUT_SECONDS = 10

# What the Worker accepts (cloudflare/newsletters/lib.js formMessage), checked here first.
ADDRESS_CHARACTERS = 254
TEXT_CHARACTERS = 4000
# Attachments, as the Worker accepts them (lib.js ATTACHMENT_*). Each is scanned for viruses before the team can open it.
FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv", "json", "docx", "xlsx"]
FILES = 3
FILE_BYTES = 5 * 1024 * 1024   # all of one message's files together
# Limits that keep the Worker's store (1000 writes a day, shared with the newsletter feed) safe.
SESSION_COOLDOWN_SECONDS = 60   # one message a minute from one visitor
SENDS_PER_WINDOW = 20           # from every visitor together, in one window
WINDOW_SECONDS = 3600

TITLE = "Contact us"
SUMMARY = "write to the team; only the team reads it, and we reply by email"
ADDRESS_LABEL = "Your email, so we can reply"
ADDRESS_PLACEHOLDER = "you@example.org"
MESSAGE_LABEL = "Message"
FILES_LABEL = "Attachments (optional)"
FILES_HELP = f"Up to {FILES} files, 5 MB in all: {', '.join(FILE_TYPES)}. Each is checked for viruses before the team opens it."
SEND = "Send message"

SENT = "Sent. We will reply to {address}."
NOT_SENT = "Not sent: {why}"
BAD_ADDRESS = "your email address does not look right. Check it and send again."
EMPTY = "the message is empty."
TOO_LONG = "the message is {length} characters long; the most is {limit}."
TOO_MANY_FILES = f"there are {{count}} attachments; the most is {FILES}."
FILES_TOO_LARGE = "the attachments are {size} MB in all; the most is 5 MB."
FILE_TYPE = "{name} is not a type the form accepts."
SESSION_WAIT ="you sent a message a moment ago. You can send another in {seconds} seconds."
CAP_WAIT = (f"many messages have arrived this hour. Try again in {{minutes}} minutes, "
            f"or write to {CONTACT_ADDRESS}.")
REFUSED = "the inbox refused it ({problem})."
NOT_SET_UP = f"the form is not set up right on our side. Please write to {CONTACT_ADDRESS}."
NO_ANSWER = f"the inbox did not answer. Try again in a few minutes, or write to {CONTACT_ADDRESS}."
