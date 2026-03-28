"""Heatmap visualization functions."""
import plotly.graph_objects as go
from viz.common import apply_theme, no_data_chart


def heat_map(df, x_col, y_col, value_col, title, color_scale="RdYlGn", zmid=None):
    """2D heatmap with color intensity representing values.
    
    Args:
        df: DataFrame with the data
        x_col: Column for x-axis categories
        y_col: Column for y-axis categories
        value_col: Column for cell values (color intensity)
        title: Chart title
        color_scale: Plotly color scale name
        zmid: Midpoint for diverging color scale
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return no_data_chart(title)
    
    try:
        # Pivot the DataFrame
        pivot_df = df.pivot(index=y_col, columns=x_col, values=value_col)
        
        if pivot_df.empty:
            return no_data_chart(title)
        
        # Calculate zmid if not provided
        if zmid is None:
            zmid = pivot_df.values.flatten().mean() if not pivot_df.empty else 0
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_df.values,
            x=pivot_df.columns,
            y=pivot_df.index,
            colorscale=color_scale,
            zmid=zmid,
            text=pivot_df.values,
            texttemplate="%{text:.1f}",
            hovertemplate="%{y} — %{x}: %{z:.2f}<extra></extra>",
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=x_col.replace("_", " ").title(),
            yaxis_title=y_col.replace("_", " ").title(),
        )
        
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")
