from streamlit import markdown


def add_custom_css(css: str = ""):
    markdown(
        f"""
        <style>
        {css}
        </style>
        """,
        unsafe_allow_html=True,
    )
