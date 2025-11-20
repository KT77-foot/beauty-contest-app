# beauty_contest_app.py
#
# Streamlit web app frontend for the decentralized Beauty Contest game.
# - Commit phase: students fix a number + nonce, send only the hash.
# - Reveal phase: students later publish number + nonce so everyone can verify.
#
# Backend: Google Apps Script web app (same /exec URL as the Python clients).
# The default API URL is read from info.txt if present.

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st

# ---------------------------------------------------------------------
# Configuration: deadlines and API URL
# ---------------------------------------------------------------------

# You can adapt these dates if your instructor gave specific ones.
COMMIT_DEADLINE_UTC = datetime(2030, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
REVEAL_OPEN_UTC = datetime(2025, 10, 21, 22, 0, 0, tzinfo=timezone.utc)

# Fallback URL if info.txt is missing or malformed
API_FALLBACK = (
    "https://script.google.com/macros/s/"
    "AKfycbyNZNOE1DYNbd4GbGTISJsGrnJ4PYCuip0yjSw3Lr8KkD6-kadKI9mfpKNfiAHEWb0Osw/exec"
)


def load_default_api_url() -> str:
    """Read the Apps Script API URL from info.txt if present, else fallback."""
    try:
        txt = Path("info.txt").read_text(encoding="utf-8")
        for line in txt.splitlines():
            if line.strip().startswith("http"):
                return line.strip()
    except Exception:
        # On any problem, just use the fallback.
        pass
    return API_FALLBACK


def sha256(s: str) -> str:
    """Return the hex SHA-256 of the given string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
    """Current time in UTC."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------
# Low-level API helpers
# ---------------------------------------------------------------------
def send_commit(api_url: str, uni_id: str, number: int, nonce: str):
    """Send a commit = hash(uni_id | number | nonce) to the backend."""
    preimage = f"{uni_id}|{number}|{nonce}"
    commit_hash = sha256(preimage)
    payload = {"kind": "commit", "uni_id": uni_id, "commit": commit_hash}
    r = requests.post(api_url, json=payload, timeout=15)
    return preimage, commit_hash, r


def send_reveal(api_url: str, uni_id: str, number: int, nonce: str):
    """Send the reveal (uni_id, number, nonce) to the backend."""
    payload = {"kind": "reveal", "uni_id": uni_id, "number": number, "nonce": nonce}
    r = requests.post(api_url, json=payload, timeout=15)
    return r


def fetch_ledger(api_url: str, table: str):
    """Fetch the current table ('commits' or 'reveals') as raw text."""
    url = f"{api_url}?table={table}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text


# ---------------------------------------------------------------------
# Streamlit pages
# ---------------------------------------------------------------------
def page_commit(api_url: str):
    st.header("Commit phase – choose your number secretly")

    if now_utc() > COMMIT_DEADLINE_UTC:
        st.error("The commit deadline has passed.")
        return

    with st.form("commit_form"):
        uni_id = st.text_input("University ID").strip()
        number = st.number_input(
            "Your guess (0–100)", min_value=0, max_value=100, value=50
        )
        nonce = st.text_input("Secret nonce (SAVE IT)", type="password").strip()
        submitted = st.form_submit_button("Submit commit")

    if submitted:
        if not uni_id or not nonce:
            st.error("Please fill in all fields (University ID and nonce).")
            return

        try:
            preimage, commit_hash, resp = send_commit(
                api_url, uni_id, int(number), nonce
            )
        except Exception as e:
            st.error(f"Error while contacting the server: {e}")
            return

        st.success("Commit sent to server.")
        st.write("**Server response:**", resp.status_code, resp.text)

        st.subheader("Save this information!")
        st.code(
            f"PREIMAGE: {preimage}\nCOMMIT HASH: {commit_hash}",
            language="text",
        )
        st.info(
            "You must re-enter the **same** University ID, number, and nonce during the "
            "reveal phase so the hash matches."
        )


def page_reveal(api_url: str):
    st.header("Reveal phase – publish your number")

    if now_utc() < REVEAL_OPEN_UTC:
        st.warning("Reveal phase is not open yet.")
        return

    with st.form("reveal_form"):
        uni_id = st.text_input("University ID").strip()
        number = st.number_input(
            "Your original guess (0–100)", min_value=0, max_value=100, value=50
        )
        nonce = st.text_input("Your secret nonce", type="password").strip()
        submitted = st.form_submit_button("Submit reveal")

    if submitted:
        if not uni_id or not nonce:
            st.error("Please fill in all fields (University ID and nonce).")
            return

        try:
            resp = send_reveal(api_url, uni_id, int(number), nonce)
        except Exception as e:
            st.error(f"Error while contacting the server: {e}")
            return

        st.write("**Server response:**", resp.status_code, resp.text)


def page_ledger(api_url: str):
    st.header("Shared ledger (read-only)")

    if st.button("Load commits"):
        try:
            data = fetch_ledger(api_url, "commits")
            st.text_area("commits", data, height=300)
        except Exception as e:
            st.error(f"Error fetching commits: {e}")

    if st.button("Load reveals"):
        try:
            data = fetch_ledger(api_url, "reveals")
            st.text_area("reveals", data, height=300)
        except Exception as e:
            st.error(f"Error fetching reveals: {e}")


def page_about():
    st.header("About this app")
    st.write(
        """
This Streamlit app implements the **Beauty Contest** classroom game
using a simple *commit–reveal* protocol:

- During the *commit* phase, each student chooses a number and a secret nonce.
- The app sends only the hash of `(uni_id | number | nonce)` to the backend.
- Later, during the *reveal* phase, students publish their number and nonce.
- Everyone can verify that the hash matches the original commit.

The backend is a Google Apps Script web app that stores the commits and reveals
in a shared sheet.
"""
    )


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Beauty Contest", page_icon="🎯")

    # API URL in the sidebar (read from info.txt by default)
    if "api_url" not in st.session_state:
        st.session_state["api_url"] = load_default_api_url()

    st.sidebar.title("Menu")
    api_url = st.sidebar.text_input("API URL", value=st.session_state["api_url"])
    st.session_state["api_url"] = api_url.strip()

    page = st.sidebar.radio("Go to:", ["Commit", "Reveal", "Ledger", "About"])

    if page == "Commit":
        page_commit(api_url)
    elif page == "Reveal":
        page_reveal(api_url)
    elif page == "Ledger":
        page_ledger(api_url)
    else:
        page_about()


if __name__ == "__main__":
    main()
