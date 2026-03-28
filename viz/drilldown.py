"""Drilldown visualization functions."""
import plotly.graph_objects as go
from viz.common import apply_theme, no_data_chart


def drilldown_table(summary_df, summary_x, summary_y, title):
    """Summary bar chart designed to work with a companion selectbox for drill-down.
    
    The page code handles the selectbox and detail table rendering.
    This function just renders the summary visualization.
    """
    if summary_df.empty:
        return no_data_chart(title)
    
    try:
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=summary_df[summary_y],
            y=summary_df[summary_x],
            orientation="h",
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=summary_y.replace("_", " ").title(),
            yaxis_title=summary_x.replace("_", " ").title(),
        )
        
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")
