"""Scatter plot visualization functions."""
import plotly.graph_objects as go
import numpy as np
from viz.common import apply_theme, no_data_chart


def scatter_correlation(df, x_col, y_col, title, color_col=None, size_col=None,
                        show_regression=True, stats_dict=None):
    """Scatter plot with optional regression line and statistical annotations.
    
    Args:
        df: DataFrame with x and y data
        x_col: Column name for x-axis values
        y_col: Column name for y-axis values
        title: Chart title
        color_col: Column name for categorical coloring
        size_col: Column name for point sizing
        show_regression: Whether to fit and show OLS regression line
        stats_dict: Pre-computed stats dict with keys 'r_value', 'p_value', 'r_squared'
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return no_data_chart(title)
    
    try:
        fig = go.Figure()
        
        # Main scatter plot
        if color_col and color_col in df.columns:
            # Separate traces per category
            for category in df[color_col].unique():
                mask = df[color_col] == category
                subset = df[mask]
                
                fig.add_trace(go.Scatter(
                    x=subset[x_col], y=subset[y_col],
                    mode="markers",
                    name=str(category),
                    marker=dict(size=subset[size_col] if size_col else 8),
                ))
        else:
            fig.add_trace(go.Scatter(
                x=df[x_col], y=df[y_col],
                mode="markers",
                name="Data",
                marker=dict(size=df[size_col] if size_col else 8),
            ))
        
        # Regression line if requested
        if show_regression:
            x_vals = df[x_col].values
            y_vals = df[y_col].values
            
            # Remove NaN values
            mask = ~(np.isnan(x_vals) | np.isnan(y_vals))
            x_clean = x_vals[mask]
            y_clean = y_vals[mask]
            
            if len(x_clean) >= 2:
                # Fit regression line
                z = np.polyfit(x_clean, y_clean, 1)
                p = np.poly1d(z)
                x_line = np.linspace(x_clean.min(), x_clean.max(), 100)
                y_line = p(x_line)
                
                fig.add_trace(go.Scatter(
                    x=x_line, y=y_line,
                    mode="lines",
                    name="Regression",
                    line=dict(color="red", dash="dash"),
                    showlegend=True,
                ))
        
        # Statistical annotation
        if stats_dict:
            r_val = stats_dict.get('r_value', 0)
            p_val = stats_dict.get('p_value', 0)
            r_sq = stats_dict.get('r_squared', 0)
            
            # Format p-value
            if p_val < 0.001:
                p_str = f"{p_val:.2e}"
            else:
                p_str = f"{p_val:.4f}"
            
            annotation_text = f"R² = {r_sq:.3f}<br>p = {p_str}<br>r = {r_val:.3f}"
            
            fig.add_annotation(
                text=annotation_text,
                xref="paper", yref="paper",
                x=0.05, y=0.95,
                showarrow=False,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="gray",
                borderwidth=1,
                font=dict(size=12),
            )
        
        fig.update_layout(
            title=title,
            xaxis_title=x_col.replace("_", " ").title(),
            yaxis_title=y_col.replace("_", " ").title(),
            hovermode="closest",
        )
        
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")
