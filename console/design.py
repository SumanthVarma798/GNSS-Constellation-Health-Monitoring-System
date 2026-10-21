"""System design: the whole system in one picture, explained in simple terms with the technical details that matter.

The picture and its words are ui/components/system_design.{html,py}, a summary of docs/system-design.md.
"""
import streamlit as st
from streamlit.components.v1 import html

from console import common
from evidence import assistant
from evidence.assistant_settings import MODEL
from evidence.console_settings import JOBS, TESTS_WORKFLOW
from evidence.decision_settings import REPOSITORY
from evidence.source_overview import overview
from ui import console
from ui.components.system_design import PARTS, system_design_html

HEIGHT = 1000   # the picture, the steps and the longest card on a wide screen; a phone scrolls inside the frame
CHAT = "design_chat"   # session_state: the conversation with the assistant, [{role, content}]

seen = common.read()
sources = overview()
facts = [(f"{sources['graded'] + sources['candidates']}", f"sources known; {sources['graded']} graded"),
         (str(sum(1 for w, *_ in JOBS if w != TESTS_WORKFLOW)), "scheduled jobs, all on GitHub Actions"),
         ("0", "servers of our own"),
         (str(len(seen["prs"])), "pull requests open"), (str(len(seen["issues"])), "issues open")]

body, actions = common.layout("design", "System design", "How the system works, from the sources it reads to the change a "
                                                         "person approves. Click any part for what it does and the details behind it.")
with body:
    html(system_design_html(console.token_css(st.session_state.get("console_scheme", "auto")), console.FONT, facts),
         height=HEIGHT, scrolling=True)


@st.cache_data(ttl=60, show_spinner=False)
def model_here():
    return assistant.available()


@st.fragment
def ask_the_project():
    """Questions about the system, answered by a local model from the project's own material only."""
    st.subheader("Ask about the system")
    st.caption(f"Answers come only from the design documents, the code's own descriptions and the open issues, each "
               f"fact with its source in [brackets]. The model ({MODEL}) runs on this computer; it can still be "
               "wrong, so check the source it names.")
    if not model_here():
        st.info("Questions are off on this copy of the console: the assistant needs the local model (Ollama) on the "
                "same computer, and there is none here. On a computer that runs it, start it with `ollama serve`.")
        return
    chat = st.session_state.setdefault(CHAT, [])
    log = st.container()   # the conversation, always above the question box
    question = st.chat_input("For example: where does the orbit data come from, and how often?")
    with log:
        for turn in chat:
            st.chat_message(turn["role"]).markdown(turn["content"])
        if not question:
            return
        st.chat_message("user").markdown(question)
        text = assistant.material(seen["issues"], PARTS)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Reading the project's material…"):
                    said = st.write_stream(assistant.answer(question, chat, text))
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
