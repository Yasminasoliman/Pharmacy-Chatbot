import json
import httpx
import streamlit as st

API_URL = "http://localhost:8000/chat/stream"

st.set_page_config(page_title="Pharmacy Assistant", page_icon="💊")
st.title("💊 Pharmacy Assistant (Debug Mode)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Debug section
if "debug_info" not in st.session_state:
    st.session_state.debug_info = []

# User input
if prompt := st.chat_input("Ask about medicines..."):
    # Append user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        tool_status = st.empty()
        debug_placeholder = st.empty()

        full_response = ""
        debug_messages = []
        
        try:
            # Test basic connectivity first
            st.write("🔄 Connecting to backend...")
            
            with httpx.stream(
                "POST",
                API_URL,
                json={"message": prompt, "history": st.session_state.messages},
                timeout=90.0,
            ) as response:
                st.write(f"📡 Response status: {response.status_code}")
                
                line_count = 0
                for line in response.iter_lines():
                    line_count += 1
                    
                    data_str = line[len("data:"):].strip()
                    
                    if data_str == "[DONE]":
                        st.success("Stream complete")
                        break

                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type", "unknown")
                        
                        if event_type == "token":
                            full_response += data.get("content", "")
                            answer_placeholder.markdown(full_response + "▌")
                        elif event_type == "tool_start":
                            st.write(f"📦 Event: {event_type}")
                            name = data.get("name", "unknown")
                            inp = data.get("input", "")
                            tool_status.info(f"🔧 Calling `{name}`")
                            st.text(f"Input: {inp}")
                        elif event_type == "tool_end":
                            st.write(f"📦 Event: {event_type}")
                            name = data.get("name", "unknown")
                            out = data.get("output", "")
                            tool_status.success(f"✅ `{name}` done")
                            st.text(f"Output: {out}")
                        elif event_type == "error":
                            st.error(f"❌ Error: {data.get('message', 'Unknown error')}")
                        # else:
                            # st.json(data)  # Show unknown event types
                            
                    except json.JSONDecodeError as e:
                        pass
                
                st.write(f"📊 Total lines received: {line_count}")
                
        except Exception as e:
            st.error(f"❌ Connection error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

        # Final render
        if full_response:
            answer_placeholder.markdown(full_response)
        else:
            answer_placeholder.markdown("*No response generated*")

    # Save to history
    if full_response:
        st.session_state.messages.append({"role": "assistant", "content": full_response})