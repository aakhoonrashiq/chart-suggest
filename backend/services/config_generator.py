"""
ECharts configuration generator — produces ready-to-use ECharts option objects
from chart definitions + column mappings + dataset profile.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from models.dataset import DatasetProfile


def generate_echarts_config(
    chart: Dict[str, Any],
    mapping: Dict[str, str],
    profile: DatasetProfile,
    df: Optional[pd.DataFrame] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate an ECharts-ready option dict for a given chart and column mapping.
    Data arrays are populated from the df if provided, otherwise left empty.
    """
    cid = chart["id"]
    echarts_type = chart.get("echarts_type", "bar")

    # No config for complex custom/3D charts that need special libs
    skip_config = {
        "3d_hexagon_map", "contour_map", "deck_multilayer_map",
        "screen_grid_map", "flow_gl_vector_field",
        "3d_geographic_globe", "3d_arc_map", "3d_geo_arcs",
        "partition_map", "geo_connection_lines", "function_plot",
    }
    if cid in skip_config:
        return None

    # Helper to get data column
    def col_data(col_name: str, limit: int = 500) -> List[Any]:
        if df is None or not col_name or col_name not in df.columns:
            return []
        return df[col_name].dropna().head(limit).tolist()

    # ── Line / Area ───────────────────────────────────────────────────────────
    if cid in ("line", "area", "stepped_line", "smooth_line", "multi_x_axis_line"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        x_data = col_data(x_col)
        y_data = col_data(y_col)
        series_def: Dict[str, Any] = {"type": "line", "name": y_col, "data": y_data}
        if cid == "area":
            series_def["areaStyle"] = {}
        if cid == "stepped_line":
            series_def["step"] = "start"
        if cid == "smooth_line":
            series_def["smooth"] = True
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value"},
            "series": [series_def],
        }

    if cid in ("stacked_area", "stacked_line_chart"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        x_data = col_data(x_col)
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "name": y_col, "data": col_data(y_col), "areaStyle": {}, "stack": "total"}],
        }

    # ── Bar ───────────────────────────────────────────────────────────────────
    if cid in ("bar", "waterfall_chart", "circular_bar_chart"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": col_data(x_col)},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "name": y_col, "data": col_data(y_col)}],
        }

    if cid == "horizontal_waterfall_chart":
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": col_data(x_col)},
            "series": [{"type": "bar", "name": y_col, "data": col_data(y_col)}],
        }

    if cid in ("polar_bar", "polar_end_angle_arc_bar", "pictorial_bar"):
        cat_col = mapping.get("category", "")
        val_col = mapping.get("value", "")
        cat_data = col_data(cat_col)
        val_data = col_data(val_col)
        if cid == "pictorial_bar":
            return {
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": cat_data},
                "yAxis": {"type": "value"},
                "series": [{"type": "pictorialBar", "data": val_data,
                            "symbol": "circle", "symbolRepeatDirection": "start"}],
            }
        # polar bar
        return {
            "tooltip": {"trigger": "axis"},
            "angleAxis": {},
            "radiusAxis": {"type": "category", "data": cat_data, "z": 10},
            "polar": {},
            "series": [{"type": "bar", "data": val_data, "coordinateSystem": "polar",
                        "name": val_col, "stack": "total"}],
        }

    if cid == "range_bar_chart":
        cat_col = mapping.get("category", "")
        low_col = mapping.get("low", "")
        high_col = mapping.get("high", "")
        if df is not None and low_col in df.columns and high_col in df.columns:
            if cat_col and cat_col in df.columns:
                sub = df[[cat_col, low_col, high_col]].dropna().head(50)
                cats = sub[cat_col].astype(str).tolist()
            else:
                # No category column: use row index as labels
                sub = df[[low_col, high_col]].dropna().head(50)
                cats = [str(i + 1) for i in range(len(sub))]
            rng_data = sub[[low_col, high_col]].values.tolist()
        else:
            cats, rng_data = [], []
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": cats},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "name": f"{low_col}→{high_col}",
                        "data": rng_data, "itemStyle": {"normal": {}}}],
        }

    if cid == "bar_chart_race":
        time_col = mapping.get("time", "")
        cat_col = mapping.get("category", "")
        val_col = mapping.get("value", "")
        # Render as a simple bar for the latest time slice
        if df is not None and cat_col in df.columns and val_col in df.columns:
            grp = df.groupby(cat_col)[val_col].sum().sort_values(ascending=False).head(10)
            bar_cats = [str(c) for c in grp.index.tolist()]
            bar_vals = grp.values.tolist()
        else:
            bar_cats, bar_vals = [], []
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": bar_cats},
            "series": [{"type": "bar", "name": val_col, "data": bar_vals}],
        }

    if cid in ("progress_bar", "bullet_chart"):
        val_col = mapping.get("value", "")
        tgt_col = mapping.get("target", "")
        cat_col = mapping.get("category", "")
        val = float(df[val_col].dropna().mean()) if df is not None and val_col and val_col in df.columns else 0
        tgt = float(df[tgt_col].dropna().mean()) if df is not None and tgt_col and tgt_col in df.columns else 100
        label = cat_col or val_col
        pct = round(min(val / tgt * 100, 100), 1) if tgt else 0
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value", "max": tgt},
            "yAxis": {"type": "category", "data": [label]},
            "series": [
                {"type": "bar", "name": "Target", "data": [tgt], "barMaxWidth": 20,
                 "itemStyle": {"color": "rgba(108,99,255,0.15)"}},
                {"type": "bar", "name": "Value", "data": [val], "barMaxWidth": 20,
                 "itemStyle": {"color": "#6c63ff"}, "barGap": "-100%"},
            ],
        }

    if cid == "horizontal_bar":
        x_col = mapping.get("y", "")
        y_col = mapping.get("x", "")
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": col_data(y_col)},
            "series": [{"type": "bar", "name": x_col, "data": col_data(x_col)}],
        }

    if cid in ("stacked_bar_chart", "100_stacked_bar", "stacked_horizontal_bar", "100_stacked_horizontal_bar"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        stack_mode = "total" if "100" in cid else "total"
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {},
            "xAxis": {"type": "category", "data": col_data(x_col)},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "name": y_col, "data": col_data(y_col), "stack": stack_mode}],
        }

    if cid == "bar_with_line":
        x_col = mapping.get("x", "")
        y1 = mapping.get("bar_value", "") or mapping.get("y", "")
        y2 = mapping.get("line_value", "") or mapping.get("y2", "")
        x_data = col_data(x_col)
        y1_data = col_data(y1)
        y2_data = col_data(y2)
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [y1, y2]},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": [{"type": "value", "name": y1}, {"type": "value", "name": y2}],
            "series": [
                {"type": "bar", "name": y1, "data": y1_data},
                {"type": "line", "name": y2, "data": y2_data, "yAxisIndex": 1},
            ],
        }

    # ── Pie / Donut / Nightingale ─────────────────────────────────────────────
    if cid in ("pie", "donut", "nightingale_rose"):
        name_col = mapping.get("name", "")
        val_col = mapping.get("value", "")
        if df is not None and name_col and val_col and name_col in df.columns and val_col in df.columns:
            pie_data = [
                {"name": str(row[name_col]), "value": float(row[val_col])}
                for _, row in df[[name_col, val_col]].dropna().head(20).iterrows()
            ]
        else:
            pie_data = []
        radius = ["40%", "70%"] if cid == "donut" else "70%"
        rose_type = "area" if cid == "nightingale_rose" else None
        series_entry: Dict[str, Any] = {
            "type": "pie",
            "radius": radius,
            "data": pie_data,
            "label": {"show": True, "formatter": "{b}: {d}%"},
        }
        if rose_type:
            series_entry["roseType"] = rose_type
        return {
            "tooltip": {"trigger": "item"},
            "legend": {"orient": "vertical", "left": "left"},
            "series": [series_entry],
        }

    # ── Scatter / Bubble ──────────────────────────────────────────────────────
    if cid in ("scatter", "effect_scatter"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        if df is not None and x_col and y_col and x_col in df.columns and y_col in df.columns:
            scatter_data = df[[x_col, y_col]].dropna().head(500).values.tolist()
        else:
            scatter_data = []
        st = "scatter" if cid == "scatter" else "effectScatter"
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value", "name": x_col},
            "yAxis": {"type": "value", "name": y_col},
            "series": [{"type": st, "data": scatter_data}],
        }

    if cid == "bubble":
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        size_col = mapping.get("size", "")
        if df is not None and x_col in df.columns and y_col in df.columns:
            cols_to_use = [x_col, y_col]
            if size_col and size_col in df.columns:
                cols_to_use.append(size_col)
            bdata = df[cols_to_use].dropna().head(500).values.tolist()
        else:
            bdata = []
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value", "name": x_col},
            "yAxis": {"type": "value", "name": y_col},
            "series": [{"type": "scatter", "data": bdata,
                        "symbolSize": "function(d){return Math.sqrt(d[2]||10)*3;}"}],
        }

    # ── Heatmap ───────────────────────────────────────────────────────────────
    if cid in ("heatmap", "polar_heatmap"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        val_col = mapping.get("value", "")
        if df is not None and x_col in df.columns and y_col in df.columns and val_col in df.columns:
            hdata = df[[x_col, y_col, val_col]].dropna().head(500).values.tolist()
            x_cats = sorted(df[x_col].dropna().unique().tolist())
            y_cats = sorted(df[y_col].dropna().unique().tolist())
        else:
            hdata, x_cats, y_cats = [], [], []
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "category", "data": [str(v) for v in x_cats]},
            "yAxis": {"type": "category", "data": [str(v) for v in y_cats]},
            "visualMap": {"min": 0, "max": 100, "calculable": True},
            "series": [{"type": "heatmap", "data": hdata, "label": {"show": False}}],
        }

    if cid in ("calendar_heatmap", "calendar_chart"):
        date_col = mapping.get("date", "")
        val_col = mapping.get("value", "")
        if df is not None and date_col in df.columns and val_col in df.columns:
            sub = df[[date_col, val_col]].dropna().head(366)
            # Parse dates robustly
            try:
                sub = sub.copy()
                sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
                sub = sub.dropna(subset=[date_col])
                year = str(sub[date_col].dt.year.mode()[0]) if len(sub) > 0 else "2026"
                cal_data = [
                    [row[date_col].strftime("%Y-%m-%d"), float(row[val_col])]
                    for _, row in sub.iterrows()
                ]
            except Exception:
                year = "2026"
                cal_data = [[str(row[date_col])[:10], float(row[val_col])] for _, row in sub.iterrows()]
        else:
            cal_data, year = [], "2026"
        vals = [d[1] for d in cal_data]
        vmin, vmax = (min(vals), max(vals)) if vals else (0, 100)
        return {
            "tooltip": {"trigger": "item"},
            "visualMap": {"min": vmin, "max": vmax, "type": "piecewise"},
            "calendar": {"range": year},
            "series": [{"type": "heatmap", "coordinateSystem": "calendar", "data": cal_data}],
        }

    # ── Candlestick ───────────────────────────────────────────────────────────
    if cid == "candlestick_chart":
        date_col = mapping.get("date", "")
        open_col = mapping.get("open", "")
        close_col = mapping.get("close", "")
        low_col = mapping.get("low", "")
        high_col = mapping.get("high", "")
        if df is not None and all(c in df.columns for c in [date_col, open_col, close_col, low_col, high_col]):
            sub = df[[date_col, open_col, close_col, low_col, high_col]].dropna().head(200)
            dates = sub[date_col].astype(str).tolist()
            ohlc_data = sub[[open_col, close_col, low_col, high_col]].values.tolist()
        else:
            dates, ohlc_data = [], []
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": dates},
            "yAxis": {"type": "value"},
            "series": [{"type": "candlestick", "data": ohlc_data}],
        }

    # ── Radar ─────────────────────────────────────────────────────────────────
    if cid == "radar":
        dims = [d for d in mapping.get("dimensions", "").split(",") if d]
        if df is not None and dims:
            valid_dims = [d for d in dims if d in df.columns]
            indicators = [{"name": d, "max": float(df[d].max())} for d in valid_dims]
            # Use first row as example data point
            first_row = df[valid_dims].dropna().head(1)
            radar_data = [{"value": first_row.iloc[0].tolist(), "name": "Profile"}] if len(first_row) > 0 else []
        else:
            indicators, radar_data = [], []
        return {
            "tooltip": {},
            "legend": {},
            "radar": {"indicator": indicators},
            "series": [{"type": "radar", "data": radar_data}],
        }

    # ── Box Plot ──────────────────────────────────────────────────────────────
    if cid == "box_plot":
        cat_col = mapping.get("category", "")
        val_col = mapping.get("values", "")
        if df is not None and cat_col in df.columns and val_col in df.columns:
            grouped = df.groupby(cat_col)[val_col].apply(lambda s: s.dropna().tolist())
            cats = [str(c) for c in grouped.index.tolist()]
            bxdata = []
            for g in grouped:
                s = pd.Series(g)
                if len(s) >= 4:
                    bxdata.append([
                        float(s.min()), float(s.quantile(0.25)),
                        float(s.median()), float(s.quantile(0.75)), float(s.max())
                    ])
        else:
            cats, bxdata = [], []
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "category", "data": cats},
            "yAxis": {"type": "value"},
            "series": [{"type": "boxplot", "data": bxdata}],
        }

    # ── Sankey ────────────────────────────────────────────────────────────────
    if cid == "sankey":
        src_col = mapping.get("source", "")
        tgt_col = mapping.get("target", "")
        val_col = mapping.get("value", "")
        if df is not None and src_col in df.columns and tgt_col in df.columns:
            sub = df.dropna(subset=[src_col, tgt_col]).head(50)
            all_nodes = list(set(sub[src_col].tolist() + sub[tgt_col].tolist()))
            nodes = [{"name": str(n)} for n in all_nodes]
            if val_col in df.columns:
                links = [{"source": str(r[src_col]), "target": str(r[tgt_col]), "value": float(r[val_col])} for _, r in sub.iterrows()]
            else:
                links = [{"source": str(r[src_col]), "target": str(r[tgt_col]), "value": 1} for _, r in sub.iterrows()]
        else:
            nodes, links = [], []
        return {
            "tooltip": {"trigger": "item"},
            "series": [{"type": "sankey", "data": nodes, "links": links, "emphasis": {"focus": "adjacency"}}],
        }

    # ── Network Graph ─────────────────────────────────────────────────────────
    if cid in ("network_graph", "network_diagram"):
        src_col = mapping.get("source", "")
        tgt_col = mapping.get("target", "")
        if df is not None and src_col in df.columns and tgt_col in df.columns:
            sub = df.dropna(subset=[src_col, tgt_col]).head(100)
            all_nodes = list(set(sub[src_col].tolist() + sub[tgt_col].tolist()))
            gx_nodes = [{"name": str(n), "symbolSize": 10} for n in all_nodes]
            gx_edges = [{"source": str(r[src_col]), "target": str(r[tgt_col])} for _, r in sub.iterrows()]
        else:
            gx_nodes, gx_edges = [], []
        return {
            "tooltip": {},
            "series": [{"type": "graph", "layout": "force", "data": gx_nodes, "links": gx_edges,
                        "roam": True, "label": {"show": True}, "force": {"repulsion": 100}}],
        }

    # ── Treemap ───────────────────────────────────────────────────────────────
    if cid in ("treemap", "partition_map"):
        parent_col = mapping.get("parent", "")
        child_col = mapping.get("child", "")
        val_col = mapping.get("value", "")
        if df is not None and parent_col in df.columns:
            groups: Dict[str, Any] = {}
            for _, row in df.dropna(subset=[parent_col]).head(200).iterrows():
                p = str(row[parent_col])
                c = str(row.get(child_col, p)) if child_col and child_col in df.columns else p
                v = float(row[val_col]) if val_col and val_col in df.columns and pd.notna(row.get(val_col)) else 1
                if p not in groups:
                    groups[p] = {"name": p, "children": []}
                groups[p]["children"].append({"name": c, "value": v})
            tm_data = list(groups.values())
        else:
            tm_data = []
        return {
            "tooltip": {"trigger": "item"},
            "series": [{"type": "treemap", "data": tm_data, "roam": False, "label": {"show": True}}],
        }

    # ── Sunburst ──────────────────────────────────────────────────────────────
    if cid == "sunburst":
        parent_col = mapping.get("parent", "")
        child_col = mapping.get("child", "")
        val_col = mapping.get("value", "")
        if df is not None and parent_col in df.columns:
            groups: Dict[str, Any] = {}
            for _, row in df.dropna(subset=[parent_col]).head(200).iterrows():
                p = str(row[parent_col])
                c = str(row.get(child_col, p)) if child_col and child_col in df.columns else p
                v = float(row[val_col]) if val_col and val_col in df.columns and pd.notna(row.get(val_col)) else 1
                if p not in groups:
                    groups[p] = {"name": p, "children": []}
                groups[p]["children"].append({"name": c, "value": v})
            sb_data = list(groups.values())
        else:
            sb_data = []
        return {
            "tooltip": {"trigger": "item"},
            "series": [{"type": "sunburst", "data": sb_data, "radius": ["20%", "90%"],
                        "label": {"rotate": "radial"}}],
        }

    # ── Funnel ────────────────────────────────────────────────────────────────
    if cid == "funnel":
        name_col = mapping.get("name", "") or mapping.get("stage", "")
        val_col = mapping.get("value", "")
        if df is not None and name_col in df.columns and val_col in df.columns:
            fn_data = [{"name": str(r[name_col]), "value": float(r[val_col])}
                       for _, r in df[[name_col, val_col]].dropna().head(10).iterrows()]
        else:
            fn_data = []
        return {
            "tooltip": {"trigger": "item"},
            "series": [{"type": "funnel", "data": fn_data, "label": {"show": True, "position": "inside"}}],
        }

    # ── Gauge ─────────────────────────────────────────────────────────────────
    if cid == "gauge":
        val_col = mapping.get("value", "")
        val = 0
        if df is not None and val_col and val_col in df.columns:
            val = float(df[val_col].dropna().iloc[0]) if len(df) > 0 else 0
        return {
            "series": [{"type": "gauge", "data": [{"value": val, "name": val_col}]}],
        }

    # ── Theme River ───────────────────────────────────────────────────────────
    if cid == "theme_river":
        date_col = mapping.get("date", "")
        cat_col = mapping.get("category", "")
        val_col = mapping.get("value", "")
        if df is not None and date_col in df.columns and val_col in df.columns:
            # If no category column, create a single series
            if cat_col and cat_col in df.columns:
                sub = df[[date_col, cat_col, val_col]].dropna().head(500)
                # Get unique categories for legend
                legend_cats = sub[cat_col].unique().tolist()
                tr_data = [
                    [str(r[date_col])[:10], float(r[val_col]), str(r[cat_col])]
                    for _, r in sub.iterrows()
                ]
            else:
                # Single series — use column name as category
                sub = df[[date_col, val_col]].dropna().head(500)
                legend_cats = [val_col]
                tr_data = [
                    [str(r[date_col])[:10], float(r[val_col]), val_col]
                    for _, r in sub.iterrows()
                ]
        else:
            tr_data, legend_cats = [], []
        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": legend_cats},
            "singleAxis": {"type": "time", "bottom": "10%"},
            "series": [{"type": "themeRiver", "data": tr_data}],
        }

    # ── KPI / Big Number ──────────────────────────────────────────────────────
    if cid in ("kpi", "big_number", "big_number_total"):
        val_col = mapping.get("value", "")
        val = 0
        if df is not None and val_col and val_col in df.columns:
            val = float(df[val_col].sum())
        return {"kpi_value": val, "kpi_label": val_col, "type": "kpi"}

    # ── Geographic Region Map ─────────────────────────────────────────────────
    if cid == "geographic_region_map":
        region_col = mapping.get("region", "")
        val_col = mapping.get("value", "")
        if df is not None and region_col in df.columns and val_col in df.columns:
            map_data = [{"name": str(r[region_col]), "value": float(r[val_col])}
                        for _, r in df[[region_col, val_col]].dropna().head(200).iterrows()]
        else:
            map_data = []
        return {
            "tooltip": {"trigger": "item"},
            "visualMap": {"min": 0, "max": 100, "calculable": True},
            "series": [{"type": "map", "map": "world", "data": map_data}],
        }

    # ── 3D Scatter / GL ───────────────────────────────────────────────────────
    if cid in ("3d_scatter_plot", "3d_surface_plot", "3d_line_chart"):
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        z_col = mapping.get("z", "")
        cols = [c for c in [x_col, y_col, z_col] if c and df is not None and c in df.columns]
        if df is not None and len(cols) >= 2:
            data3d = df[cols].dropna().head(500).values.tolist()
        else:
            data3d = []
        t = "scatter3D" if "scatter" in cid else ("surface" if "surface" in cid else "line3D")
        return {
            "grid3D": {},
            "xAxis3D": {"name": x_col},
            "yAxis3D": {"name": y_col},
            "zAxis3D": {"name": z_col},
            "series": [{"type": t, "data": data3d}],
        }

    if cid == "3d_bar_chart":
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        z_col = mapping.get("value", "") or mapping.get("z", "")
        cols = [c for c in [x_col, y_col, z_col] if c and df is not None and c in df.columns]
        if df is not None and len(cols) >= 3:
            sub = df[cols].dropna().head(500)
            data3d = sub.values.tolist()
        elif df is not None and len(cols) >= 2:
            sub = df[cols].dropna().head(500)
            data3d = [[row[0], row[1], 1.0] for row in sub.values.tolist()]
        else:
            data3d = []
        return {
            "grid3D": {},
            "xAxis3D": {"type": "value", "name": x_col},
            "yAxis3D": {"type": "value", "name": y_col},
            "zAxis3D": {"type": "value", "name": z_col},
            "series": [{"type": "bar3D", "data": data3d,
                        "shading": "color",
                        "label": {"show": False}}],
        }

    if cid == "scatter_gl":
        # scatterGL is a WebGL 2D scatter — needs echarts-gl
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        if df is not None and x_col in df.columns and y_col in df.columns:
            scatter_data = df[[x_col, y_col]].dropna().head(5000).values.tolist()
        else:
            scatter_data = []
        return {
            "tooltip": {"trigger": "item"},
            "xAxis": {"type": "value", "name": x_col},
            "yAxis": {"type": "value", "name": y_col},
            "series": [{"type": "scatterGL", "data": scatter_data}],
        }

    if cid == "lines_gl":
        x_col = mapping.get("x", "")
        y_col = mapping.get("y", "")
        if df is not None and x_col in df.columns and y_col in df.columns:
            line_data = df[[x_col, y_col]].dropna().head(2000).values.tolist()
        else:
            line_data = []
        return {
            "xAxis": {"type": "value", "name": x_col},
            "yAxis": {"type": "value", "name": y_col},
            "series": [{"type": "linesGL", "data": line_data,
                        "effect": {"show": True, "period": 4, "trailLength": 0.5}}],
        }

    # ── Parallel Coordinates / Scatter Matrix / Correlation Matrix ────────────
    if cid in ("parallel_coordinates", "scatter_matrix", "correlation_matrix"):
        dims = [d.strip() for d in mapping.get("dimensions", "").split(",") if d.strip()]
        if df is not None and dims:
            valid_dims = [d for d in dims if d in df.columns]
            pc_data = df[valid_dims].dropna().head(200).values.tolist()
            dim_defs = [{"name": d, "dim": i} for i, d in enumerate(valid_dims)]
        else:
            pc_data, dim_defs, valid_dims = [], [], dims

        if cid == "parallel_coordinates":
            return {
                "tooltip": {"trigger": "axis"},
                "parallelAxis": dim_defs,
                "series": [{"type": "parallel", "data": pc_data}],
            }

        if cid == "scatter_matrix":
            # Render as a multi-series scatter chart for first 2 valid dims
            if df is not None and len(valid_dims) >= 2:
                x_d, y_d = valid_dims[0], valid_dims[1]
                sc_data = df[[x_d, y_d]].dropna().head(300).values.tolist()
            else:
                x_d = valid_dims[0] if len(valid_dims) >= 1 else ""
                y_d = valid_dims[1] if len(valid_dims) >= 2 else ""
                sc_data = []
            return {
                "tooltip": {"trigger": "item"},
                "xAxis": {"type": "value", "name": x_d},
                "yAxis": {"type": "value", "name": y_d},
                "series": [{"type": "scatter", "name": f"{x_d} vs {y_d}", "data": sc_data,
                            "symbolSize": 4}],
            }

        if cid == "correlation_matrix":
            # Build correlation heatmap
            if df is not None and len(valid_dims) >= 2:
                corr = df[valid_dims].corr()
                hm_data = [
                    [i, j, round(float(corr.iloc[i, j]), 3)]
                    for i in range(len(valid_dims))
                    for j in range(len(valid_dims))
                ]
                vmin, vmax = -1, 1
            else:
                hm_data, vmin, vmax = [], -1, 1
            return {
                "tooltip": {"trigger": "item"},
                "visualMap": {"min": vmin, "max": vmax,
                              "calculable": True,
                              "inRange": {"color": ["#313695", "#FFFAFA", "#A50026"]}},
                "xAxis": {"type": "category", "data": valid_dims, "axisLabel": {"rotate": 30}},
                "yAxis": {"type": "category", "data": valid_dims},
                "series": [{"type": "heatmap", "data": hm_data,
                            "label": {"show": True, "formatter": "{@[2]}"}}],
            }

    # ── Chord Diagram ─────────────────────────────────────────────────────────
    if cid == "chord_diagram":
        src_col = mapping.get("source", "")
        tgt_col = mapping.get("target", "")
        val_col = mapping.get("value", "")
        if df is not None and src_col in df.columns and tgt_col in df.columns:
            sub = df.dropna(subset=[src_col, tgt_col]).head(50)
            all_nodes = list(set(sub[src_col].tolist() + sub[tgt_col].tolist()))
            chord_nodes = [{"name": str(n)} for n in all_nodes]
            node_idx = {n: i for i, n in enumerate(all_nodes)}
            chord_links = []
            for _, row in sub.iterrows():
                v = float(row[val_col]) if val_col and val_col in df.columns and pd.notna(row.get(val_col)) else 1
                chord_links.append({"source": node_idx.get(str(row[src_col]), 0),
                                    "target": node_idx.get(str(row[tgt_col]), 0), "value": v})
        else:
            chord_nodes, chord_links = [], []
        return {
            "tooltip": {},
            "series": [{"type": "graph", "layout": "circular", "data": chord_nodes,
                        "links": chord_links, "roam": True, "circular": {"rotateLabel": True}}],
        }

    # ── Table ─────────────────────────────────────────────────────────────────
    if cid in ("table", "pivot_table"):
        cols = mapping.get("columns", "").split(",")
        if df is not None:
            valid_cols = [c for c in cols if c in df.columns]
            rows = df[valid_cols].head(20).fillna("").values.tolist() if valid_cols else []
        else:
            valid_cols, rows = cols, []
        return {"type": "table", "columns": valid_cols, "rows": rows}

    # ── Tree Chart ────────────────────────────────────────────────────────────
    if cid == "tree_chart":
        parent_col = mapping.get("parent", "")
        child_col = mapping.get("child", "")
        if df is not None and parent_col in df.columns:
            groups: Dict[str, Any] = {}
            for _, row in df.dropna(subset=[parent_col]).head(100).iterrows():
                p = str(row[parent_col])
                c = str(row[child_col]) if child_col and child_col in df.columns and pd.notna(row.get(child_col)) else p
                if p not in groups:
                    groups[p] = {"name": p, "children": []}
                groups[p]["children"].append({"name": c})
            # Build root node
            tree_data = [{"name": "Root", "children": list(groups.values())}]
        else:
            tree_data = [{"name": "Root", "children": []}]
        return {
            "tooltip": {"trigger": "item"},
            "series": [{
                "type": "tree",
                "data": tree_data,
                "top": "5%", "left": "10%", "bottom": "5%", "right": "10%",
                "symbolSize": 7,
                "label": {"position": "left", "verticalAlign": "middle", "fontSize": 11},
                "leaves": {"label": {"position": "right", "verticalAlign": "middle"}},
                "expandAndCollapse": True,
                "animationDuration": 550,
            }],
        }

    # ── Polar Line ────────────────────────────────────────────────────────────
    if cid == "polar_line":
        x_col = mapping.get("x", "") or mapping.get("category", "")
        y_col = mapping.get("y", "") or mapping.get("value", "")
        x_data = col_data(x_col)
        y_data = col_data(y_col)
        return {
            "tooltip": {"trigger": "axis"},
            "angleAxis": {"type": "category", "data": x_data},
            "radiusAxis": {},
            "polar": {},
            "series": [{"type": "line", "data": y_data, "coordinateSystem": "polar"}],
        }

    # ── Bump Chart ────────────────────────────────────────────────────────────
    if cid == "bump_chart":
        time_col = mapping.get("time", "")
        cat_col = mapping.get("category", "")
        rank_col = mapping.get("rank", "")
        # Render as a line chart of rank over time for one category
        if df is not None and time_col in df.columns and rank_col in df.columns:
            x_data = col_data(time_col)
            y_data = col_data(rank_col)
        elif df is not None and time_col in df.columns:
            x_data = col_data(time_col)
            y_data = []
        else:
            x_data, y_data = [], []
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value", "inverse": True, "name": "Rank"},
            "series": [{"type": "line", "data": y_data, "smooth": True,
                        "lineStyle": {"width": 3}, "symbol": "circle", "symbolSize": 8}],
        }

    # ── Confidence Band Line ──────────────────────────────────────────────────
    if cid == "confidence_band_line":
        x_col = mapping.get("x", "") or mapping.get("date", "")
        y_col = mapping.get("y", "") or mapping.get("value", "")
        x_data = col_data(x_col)
        y_data = col_data(y_col)
        # Render as line with shaded area for confidence
        upper = [v * 1.1 if isinstance(v, (int, float)) else v for v in y_data]
        lower = [v * 0.9 if isinstance(v, (int, float)) else v for v in y_data]
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value"},
            "series": [
                {"type": "line", "name": y_col, "data": y_data, "smooth": True},
                {"type": "line", "name": "Upper Band", "data": upper, "lineStyle": {"opacity": 0},
                 "areaStyle": {"color": "rgba(108,99,255,0.15)"}, "stack": "confidence"},
                {"type": "line", "name": "Lower Band", "data": lower, "lineStyle": {"opacity": 0},
                 "areaStyle": {"color": "rgba(108,99,255,0.05)"}, "stack": "confidence"},
            ],
        }

    # ── Error Bar Chart ───────────────────────────────────────────────────────
    if cid == "error_bar_chart":
        x_col = mapping.get("x", "") or mapping.get("category", "")
        y_col = mapping.get("y", "") or mapping.get("value", "")
        x_data = col_data(x_col)
        y_data = col_data(y_col)
        # Simulate error bars with scatter + custom bar series
        err_data = [[v * 0.9, v * 1.1] if isinstance(v, (int, float)) else [0, 0] for v in y_data]
        return {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value"},
            "series": [
                {"type": "bar", "name": y_col, "data": y_data},
                {"type": "custom", "name": "Error", "data": err_data,
                 "renderItem": "function(params,api){var x=api.coord([api.value(0),0])[0];var high=api.coord([0,api.value(1)])[1];var low=api.coord([0,api.value(2)])[1];return {type:'line',transition:['shape'],shape:{x1:x,y1:high,x2:x,y2:low},style:{stroke:api.visual('color'),lineWidth:2}};}"},
            ],
        }

    # Fallback — no config available
    return None
