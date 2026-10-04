import streamlit as st

import rag  # ai/rag.py (ai/ is on sys.path, see app.py)
from nomad.data import connection, query

st.title("Chat with reviews")
st.caption("Retrieval-augmented generation: your question is embedded with Gemini, the closest reviews "
           "are found inside Snowflake with VECTOR_COSINE_SIMILARITY, and Gemini answers from those "
           "reviews only, citing them. Ask in any language — reviews are multilingual too.")

cities = query("select city, city_name from DIM_CITIES order by city_name")
choice = st.selectbox("City", ["All cities"] + cities.city_name.tolist())
city = None if choice == "All cities" else cities.set_index("city_name").city[choice]

if "chat" not in st.session_state:
    st.session_state.chat = []

for turn in st.session_state.chat:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn.get("sources"):
            with st.expander(f"{len(turn['sources'])} reviews used"):
                for i, h in enumerate(turn["sources"], 1):
                    st.markdown(f"**[{i}]** {h['city']} · {h['review_date']} · similarity {h['score']:.2f}")
                    st.caption(h["comment_text"])

question = st.chat_input("e.g. Is it noisy at night? What do guests say about check-in?")
if question:
    st.session_state.chat.append({"role": "user", "content": question})
    with st.spinner("Searching reviews and writing an answer…"):
        hits = rag.search(question, k=8, city=city, conn=connection())
        reply = rag.answer(question, hits) if hits else "No indexed reviews match that filter yet."
    st.session_state.chat.append({"role": "assistant", "content": reply, "sources": hits})
    st.rerun()
