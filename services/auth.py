import streamlit as st

def check_password():
    """Wymusza logowanie hasłem zdefiniowanym w secrets."""
    if st.secrets.get("APP_PASSWORD") is None:
        # Jeśli nie ustawiono hasła w secrets, pozwalamy działać
        return True

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Nie przechowujemy hasła
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Pierwsze uruchomienie
        st.text_input("Podaj hasło dostępu:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Błędne hasło
        st.text_input("Podaj hasło dostępu:", type="password", on_change=password_entered, key="password")
        st.error("😕 Niepoprawne hasło")
        return False
    else:
        # Hasło poprawne
        return True
