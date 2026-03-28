"""Comparison visualization functions."""
import plotly.graph_objects as go
from viz.common import apply_theme, no_data_chart, format_stat_label


def split_comparison(df, category_col, value_cols, title, chart_type="bar", labels=None):
    """Grouped bar or line chart comparing values across categories.
    
    Args:
        df: DataFrame with categories and values
        category_col: Column name for x-axis categories
        value_cols: List of column names to plot (or single string)
        title: Chart title
        chart_type: 'bar' or 'line'
        labels: Optional dict mapping column names to display labels
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return no_data_chart(title)
    
    try:
        # Handle single value column
        if isinstance(value_cols, str):
            value_cols = [value_cols]
        
        fig = go.Figure()
        
        for col in value_cols:
            if col not in df.columns:
                continue
            
            label = labels.get(col, col) if labels else format_stat_label(col)
            
            if chart_type == "line":
                fig.add_trace(go.Scatter(
                    x=df[category_col], y=df[col],
                    mode="lines+markers",
                    name=label,
                ))
            else:  # bar
                fig.add_trace(go.Bar(
                    x=df[category_col], y=df[col],
                    name=label,
                ))
        
        fig.update_layout(
            title=title,
            xaxis_title=category_col.replace("_", " ").title(),
            yaxis_title="Value",
            barmode="group" if chart_type == "bar" else None,
            hovermode="x unified",
        )
        
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")


def radar_chart(df, categories_col, values_cols, labels, title):
    """Spider/radar chart for multi-stat comparison.
    
    Args:
        df: DataFrame where each row is a stat
        categories_col: Column containing category labels (stat names)
        values_cols: List of column names to plot as separate traces (one per entity)
        labels: List of trace labels (e.g., player names)
        title: Chart title
    
    Returns:
        plotly.graph_objects.Figure
    """
    if df.empty:
        return no_data_chart(title)
    
    try:
        fig = go.Figure()
        
        categories = df[categories_col].tolist()
        
        for i, val_col in enumerate(values_cols):
            if val_col not in df.columns:
                continue
            
            values = df[val_col].tolist()
            
            # Normalize values to 0-100 range
            min_val = min(values)
            max_val = max(values)
            range_val = max_val - min_val if max_val > min_val else 1
            normalized = [(v - min_val) / range_val * 100 for v in values]
            
            # Close the polygon by repeating the first value
            normalized_closed = normalized + [normalized[0]]
            categories_closed = categories + [categories[0]]
            
            fig.add_trace(go.Scatterpolar(
                r=normalized_closed,
                theta=categories_closed,
                fill="toself",
                fillcolor="rgba(0,0,255,0.2)" if i == 0 else "rgba(255,0,0,0.2)",
                name=labels[i] if i < len(labels) else f"Series {i+1}",
            ))
        
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title=title,
            showlegend=True,
        )
        
        return apply_theme(fig)
    except Exception as e:
        return no_data_chart(title, f"Error: {str(e)}")
