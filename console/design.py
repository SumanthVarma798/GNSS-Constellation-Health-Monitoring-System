"""System design: the whole system in one picture, explained in simple terms with the technical details that matter.

The picture and its words are ui/components/system_design.{html,py}, a summary of docs/system-design.md.
"""
import streamlit as st
from streamlit.components.v1 import html

from console import common
from evidence import assistant
from evidence.assistant_settings import MODEL, OLLAMA_URL, SECRETS_SECTION
from evidence.console_settings import JOBS, TESTS_WORKFLOW
from evidence.decision_settings import REPOSITORY
from evidence.source_overview import overview
from ui import console
from ui.components.hosting import hosting_html
from ui.components.system_design import PARTS, facts_strip_html, system_design_html

HEIGHT = 960   # the picture, the steps and the longest card on a wide screen; a phone scrolls inside the frame
HOST_HEIGHT = 620
FACTS_HEIGHT = 88
CHAT = "design_chat"   # session_state: the conversation with the assistant, [{role, content}]

body, actions = common.layout("design", "System design", "How the system works, from the sources it reads to the change a "
                                                         "person approves. Click any part for what it does and the details behind it.")
tokens = console.token_css(st.session_state.get("console_scheme", "auto"))
font = console.FONT


def live_facts(seen):
    sources = overview()
    return [(f"{sources['graded'] + sources['candidates']}", f"sources known; {sources['graded']} graded"),
            (str(sum(1 for w, *_ in JOBS if w != TESTS_WORKFLOW)), "scheduled jobs, all on GitHub Actions"),
            ("0", "servers of our own"),
            (str(len(seen["prs"])), "pull requests open"), (str(len(seen["issues"])), "issues open")]


with body:
    html(system_design_html(tokens, font), height=HEIGHT, scrolling=True)


@st.fragment
def live_figures_from_github():
    seen = common.read()
    html(facts_strip_html(tokens, font, live_facts(seen)), height=FACTS_HEIGHT, scrolling=True)   # on a phone the figures wrap into rows
    st.caption(f"Live figures, read from GitHub at {seen['read_at']:%H:%M} UTC.")


with body:   # both pictures first: neither needs GitHub, so neither waits for it
    st.subheader("How it is hosted")
    st.caption("Where each public name points, and what redeploys when main changes. Click any box for details.")
    html(hosting_html(tokens, font), height=HOST_HEIGHT, scrolling=True)
    live_figures_from_github()


def where_the_model_is():
    """(url, key): the shared copy's [assistant] secrets when set, else the Ollama on this computer, with no key."""
    try:
        place = st.secrets.get(SECRETS_SECTION, {})
    except FileNotFoundError:
        place = {}
    return place.get("url", OLLAMA_URL).rstrip("/"), place.get("key", "")


@st.cache_data(ttl=60, show_spinner=False)
def model_here(url, key):
    return assistant.available(url, key)


@st.fragment
def ask_the_project():
    """Questions about the system, answered by a local model from the project's own material only."""
    st.subheader("Ask about the system")
    url, key = where_the_model_is()
    if not model_here(url, key):
        st.info("Questions are off on this copy of the console: the assistant needs the local model (Ollama) on the "
                "same computer, and there is none here. On a computer that runs it, start it with `ollama serve`.")
        return
    runs_on = "this computer" if url == OLLAMA_URL else "a team member's computer, reached through a private tunnel"
    st.caption(f"Answers come only from the design documents, the code's own descriptions and the open issues, each "
               f"fact with its source in [brackets]. The model ({MODEL}) runs on "
               f"{runs_on}; it can still be "
               "wrong, so check the source it names.")
    chat = st.session_state.setdefault(CHAT, [])
    if chat and st.button("Start over", key="design_chat_start_over", icon=":material/restart_alt:"):
        st.session_state[CHAT] = []
        st.rerun()
    log = st.container()   # the conversation, always above the question box
    question = st.chat_input("For example: where does the orbit data come from, and how often?")
    with log:
        for turn in chat:
            st.chat_message(turn["role"]).markdown(turn["content"])
        if not question:
            return
        st.chat_message("user").markdown(question)
        seen = common.read()
        text = assistant.material(seen["issues"], PARTS)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Reading the project's material…"):
                    said = st.write_stream(assistant.answer(question, chat, text, url, key))
            except assistant.Unavailable as error:
                st.error(str(error))
                return
            if unknown := assistant.unknown_sources(said, text):
                st.warning("This answer names sources the material does not have, so treat those parts with care: "
                           + ", ".join(unknown))
    chat += [{"role": "user", "content": question}, {"role": "assistant", "content": said}]


with body:
    ask_the_project()

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">More</p>')
    st.link_button("The design document", f"https://github.com/{REPOSITORY}/blob/main/docs/system-design.md",
                   icon=":material/open_in_new:")
