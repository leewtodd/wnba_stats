"""Chart and DataFrame rendering components."""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def render_chart(fig: go.Figure, key: str, height: int = 500):
    """Render a Plotly figure in Streamlit with consistent sizing.
    
    Args:
        fig: Plotly Figure object
        key: Unique key for the Streamlit element
        height: Chart height in pixels
    """
    st.plotly_chart(fig, width="stretch", key=key, height=height)


def render_dataframe(df: pd.DataFrame, title: str = None):
    """Render a DataFrame in Streamlit with optional title and formatting.
    
    Args:
        df: DataFrame to display
        title: Optional caption above the table
    """
    if title:
        st.caption(title)
    
    if df.empty:
        st.info("No data available for the selected filters.")
        return
    
    st.dataframe(df, width="stretch", hide_index=True)
