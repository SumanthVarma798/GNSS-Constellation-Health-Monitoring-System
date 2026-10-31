"""Ask: questions about the system, answered by the console's assistant (evidence/assistant.py) in plain words, only
from the project's own material, each fact with its source. Which model answers is set in the console's secrets
(evidence/assistant_settings.py)."""
import streamlit as st

from console import common
from evidence import assistant
from evidence.assistant_settings import DEEPSEEK, DEEPSEEK_URL, EXAMPLES, OLLAMA, OLLAMA_URL, SECRETS_SECTION
from ui.components.system_design import PARTS

CHAT = "ask_chat"   # session_state: the conversation, [{role, content}]

body, actions = common.layout("ask", "Ask", "Questions about the system, answered in plain words from the project's "
                                            "own documents.")


def where_the_model_is():
    """(provider, url, key) from the console's [assistant] secrets; without them, the Ollama on this computer."""
    try:
        place = st.secrets.get(SECRETS_SECTION, {})
    except FileNotFoundError:
        place = {}
    provider = str(place.get("provider", OLLAMA)).strip().lower()
    url = place.get("url", DEEPSEEK_URL if provider == DEEPSEEK else OLLAMA_URL)
    return provider, url.rstrip("/"), place.get("key", "")


@st.cache_data(ttl=60, show_spinner=False)
def model_here(url, key, provider):
    return assistant.available(url, key, provider)


def off_because(provider, url, key):
    """Why questions are off on this copy, in plain words, or None when the model can be asked."""
    if provider not in (OLLAMA, DEEPSEEK):
        return f'Questions are off: [{SECRETS_SECTION}] provider in the console\'s secrets must be "{DEEPSEEK}" or "{OLLAMA}".'
    if model_here(url, key, provider):
        return None
    if provider == DEEPSEEK:
        return (f"Questions are off: [{SECRETS_SECTION}] key in the console's secrets is empty. It needs a DeepSeek API "
                "key.")
    return ("Questions are off on this copy of the console: the assistant needs the local model (Ollama) on the same "
            "computer, and there is none here. On a computer that runs it, start it with `ollama serve`.")


def note(provider, url):
    runs_on = ("DeepSeek's hosted service, so each question goes to DeepSeek with that material" if provider == DEEPSEEK
               else "this computer" if url == OLLAMA_URL else "a team member's computer, reached through a private tunnel")
    return (f"Answers come only from the project's own documents, the code's own descriptions, its source lists and its "
            f"open issues, each fact with its source in [brackets]. The model ({assistant.model_name(provider)}) runs on "
            f"{runs_on}. It can still be wrong, so check the source it names.")


def ask(question, chat, url, key, provider):
    """Show the question and the answer as it is written; keep both in the conversation once it is whole."""
    st.chat_message("user").markdown(question)
    text = assistant.material(common.read()["issues"], PARTS)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Reading the project's material…"):
                said = st.write_stream(assistant.answer(question, chat, text, url, key, provider))
        except assistant.Unavailable as error:
            st.error(str(error))
            return
        if unknown := assistant.unknown_sources(said, text):
            st.warning("This answer names sources the material does not have, so treat those parts with care: "
                       + ", ".join(unknown))
    chat += [{"role": "user", "content": question}, {"role": "assistant", "content": said}]


def conversation(chat, url, key, provider):
    st.caption(note(provider, url))
    picked = None
    with st.container(key="ask_examples"):   # laid out as a wrapping row by ui/console.css
        for n, example in enumerate(EXAMPLES):
            if st.button(example, key=f"ask_example_{n}"):
                picked = example
    log = st.container()   # the conversation, always above the question box
    question = st.chat_input("Ask about the system, for example: where does the orbit data come from?") or picked
    with log:
        for turn in chat:
            st.chat_message(turn["role"]).markdown(turn["content"])
        if question:
            ask(question, chat, url, key, provider)


provider, url, key = where_the_model_is()
with body:
    if why := off_because(provider, url, key):
        st.info(why)
    else:
        conversation(st.session_state.setdefault(CHAT, []), url, key, provider)

with actions:   # after the conversation, so Start over shows as soon as there is one
    common.refresh_action()
    if st.session_state.get(CHAT):   # emptied before the next run draws anything
        st.button("Start over", key="ask_start_over", icon=":material/restart_alt:",
                  on_click=lambda: st.session_state.update({CHAT: []}))
    st.html('<p class="c-actions-sub">Go to</p>')
    st.page_link("console/design.py", label="System design", icon=":material/account_tree:")
