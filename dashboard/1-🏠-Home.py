from mimetypes import init
import streamlit as st

from dashboard.util import add_custom_css


class WelcomePage:
    def __init__(self):
        self.user = None

    def write(self):
        st.title("Blapp")
        st.write("A collection of Handy and Fun tools. Use the pages at your own risk!")

        st.warning(
            "This is a beta version of Blapp. Please report any bugs to the github repository."
        )


def start_app():
    welcome_page = WelcomePage()
    welcome_page.write()
    add_custom_css()

    # st.sidebar.title("Blapp")
    # st.sidebar.subheader("Welcome to Blapp!")


if __name__ == "__main__":
    st.set_page_config(
        page_title="Blapp",
        page_icon="https://raw.githubusercontent.com/Blastorios/Blastorios/master/images/B-logo.svg",  # put into dotenv?
        layout="wide",
        initial_sidebar_state="auto",
    )  # MUST be called first.

    start_app()
