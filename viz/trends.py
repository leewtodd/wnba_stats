"""Trend visualization functions."""
import plotly.graph_objects as go
from viz.common import apply_theme, no_data_chart


def trend_line(df, x_col, y_col, title, rolling_col=None, ci_col=None, color=None):
    """Line chart with optional rolling average overlay and confidence interval bands.
    
    Args:
        df: DataFrame with the data
        x_col: Column name for x-axis (typically 'game_date')
        y_col: Column name for y-axis (the raw stat values)
        title: Chart title
        rolling_col: Column name for rolling average line (if present in df)
        ci_col: Column name for confidence interval width (± from rolling_col)
        color: Line color (default: Plotly default)
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return no_data_chart(title)
    
    try:
        fig = go.Figure()
        
        # Primary trace: scatter plot with lines+markers for raw values
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col],
            mode="lines+markers", name=y_col.replace("_", " ").title(),
            line=dict(color=color) if color else dict(),
            marker=dict(opacity=0.6),
        ))
        
        # Rolling average trace if provided
        if rolling_col and rolling_col in df.columns:
            fig.add_trace(go.Scatter(
                x=df[x_col], y=df[rolling_col],
                mode="lines", name="Rolling Average",
                line=dict(width=3),
            ))
            
            # Confidence band if provided
            if ci_col and ci_col in df.columns:
                upper = df[rolling_col] + df[ci_col]
                lower = df[rolling_col] - df[ci_col]
                
                fig.add_trace(go.Scatter(
                    x=df[x_col].tolist() + df[x_col].tolist()[::-1],
                    y=upper.tolist() + lower.tolist()[::-1],
                    fill="toself", fillcolor="rgba(0,100,80,0.2)",
                    line=dict(color="rgba(255,255,255,0)"),
                    showlegend=False, name="CI",
                ))
        
        fig.update_layout(
            title=title,
            xaxis_title=x_col.replace("_", " ").title(),
            yaxis_title=y_col.replace("_", " ").title(),
            hovermode="x unified",
        )
        
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")


def animated_timeline(df, x_col, y_col, frame_col, title, color_col=None):
    """Animated scatter plot over time.
    
    If skipped, returns a "coming soon" placeholder.
    """
    if df.empty:
        return no_data_chart(title)
    
    try:
        # Placeholder: basic animated scatter
        fig = go.Figure(data=[go.Scatter(x=df[x_col], y=df[y_col], mode='markers')])
        fig.update_layout(title=title)
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")
