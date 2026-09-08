# Chart Suggest

> **Intelligent CSV-to-Chart Recommendation Engine** — Upload any CSV, get ranked chart recommendations from the complete Apache ECharts catalog with column mappings and ready-to-use ECharts configurations.

---

## Architecture

```
chart-suggest/
├── backend/
│   ├── main.py                        # FastAPI app (startup, CORS, routes, static files)
│   ├── requirements.txt
│   ├── catalog/
│   │   └── chart_catalog.json         # Compiled from Excel (81 charts, loaded at startup)
│   ├── api/routes/
│   │   └── recommend.py               # POST /recommend-charts (single consolidated API)
│   ├── services/
│   │   ├── csv_service.py             # CSV loading, validation, in-memory store
│   │   ├── profiler.py                # Column profiling, stats, signal detection
│   │   ├── type_detector.py           # 5-step semantic type classifier
│   │   ├── relationship_detector.py   # Dataset relationship pattern detection
│   │   ├── chart_matcher.py           # Catalog loading + recommendation pipeline
│   │   ├── scoring_engine.py          # 100-point scoring model + column mapping
│   │   └── config_generator.py       # ECharts option generator
│   └── models/
│       ├── dataset.py                 # DatasetProfile, ColumnProfile Pydantic models
│       └── recommendation.py         # ChartRecommendation, RecommendationResponse
├── frontend/
│   ├── index.html                     # Single-page app
│   ├── css/style.css                  # Premium dark design system
│   └── js/app.js                      # Upload flow, rendering, chart modal
├── tests/
│   ├── test_datasets/                 # 8 test CSVs (categorical, timeseries, 3D, geo, flow...)
│   ├── test_profiler.py
│   ├── test_scoring.py
│   └── test_api.py
├── scripts/
│   └── build_catalog.py              # Excel → JSON catalog compiler
└── apache_echarts_chart_catalog_final.xlsx
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt
pip install streamlit requests

# 2. Start the FastAPI backend
cd backend
uvicorn main:app --reload --port 8000

# 3. Start the Streamlit frontend (in a separate terminal)
streamlit run frontend/app.py
```

Open `http://localhost:8501` to use the interactive application.
The catalog is compiled from the Excel workbook at startup automatically if `chart_catalog.json` is missing.

---

## API Architecture — Single Public POST API

The entire chart recommendation pipeline is consolidated behind **one public API endpoint**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/recommend-charts` | Complete recommendation workflow: upload, profile, detect semantics/relationships, score, rank, and select Top-N |
| `GET`  | `/docs` | Auto-generated OpenAPI interactive documentation |

### Primary Workflow: `POST /recommend-charts`

Accepts a CSV file and an optional `top_n` parameter. Performs the complete workflow in a single request and returns recommendation metadata without rendering overhead.

**Request:**
- `Content-Type: multipart/form-data`
- `file`: CSV file (required)
- `top_n`: Integer (optional, defaults to `DEFAULT_TOP_N=5`, range 1–30)

```bash
curl -X POST http://localhost:8000/recommend-charts \
  -F "file=@house_price_dataset.csv" \
  -F "top_n=5"
```

**Response Example:**
```json
{
  "success": true,
  "dataset": {
    "filename": "house_price_dataset.csv",
    "rows": 1200,
    "columns": 6
  },
  "profile": {
    "columns": {
      "LotArea": { "semantic_type": "integer", "unique_count": 1147, "missing_pct": 0.0 },
      "SalePrice": { "semantic_type": "integer", "unique_count": 1050, "missing_pct": 0.0 }
    },
    "signals": {
      "has_datetime": false,
      "has_numeric": true,
      "has_categorical": false,
      "has_geo_latlon": false,
      "has_flow": false,
      "has_hierarchy": false,
      "has_ohlc": false
    }
  },
  "relationships_detected": ["two_numeric", "three_or_more_numeric"],
  "total_charts_evaluated": 81,
  "total_charts_eligible": 59,
  "top_n": 5,
  "recommendations": [
    {
      "rank": 1,
      "chart_id": "table",
      "chart_name": "Table",
      "chart_type": "table",
      "chart_type_label": "TABLE",
      "category": "Table",
      "score": 100,
      "confidence": "high",
      "reason": "Always suitable for raw tabular data exploration.",
      "mapping": {
        "columns": "LotArea,Bedrooms,Bathrooms,HouseAge,DistanceToCityCenter,SalePrice"
      }
    },
    {
      "rank": 2,
      "chart_id": "scatter",
      "chart_name": "Scatter",
      "chart_type": "scatter",
      "chart_type_label": "SCATTER PLOT",
      "category": "Scatter Charts",
      "score": 90,
      "confidence": "high",
      "reason": "Strong correlation between two numeric variables (LotArea vs Bedrooms).",
      "mapping": {
        "x": "LotArea",
        "y": "Bedrooms"
      }
    }
  ]
}
```

---


## Chart Catalog

The Excel workbook contains **27 sheets** with **81 unique chart definitions**:

| Category | Charts |
|----------|--------|
| Bar Charts | Bar, Waterfall, Polar Bar, Bar Race, Range Bar, Stacked Bar, Horizontal Bar, 100% Stacked, Progress Bar, Bar+Line, Error Bar, Pictorial, and more |
| Line Charts | Line, Area, Stepped, Smooth, Polar Line, Stacked Area, Bump Chart, Confidence Band, 3D Line |
| Pie Charts | Pie, Donut, Nightingale Rose |
| Scatter | Scatter, Bubble, Effect Scatter, Scatter Matrix, 3D Scatter |
| Map | Geographic Region Map, Geo Connection Lines, 3D Globe, 3D Arc Map, Heatmap (geo), 3D Scatter Map, Contour, Deck Multi-layer |
| Specialized | Candlestick, Radar, Box Plot, Bullet Chart |
| Heatmap | Heatmap, Calendar Heatmap, Polar Heatmap |
| Graph | Network Graph, Network Diagram |
| Tree/Hierarchy | Tree Chart, Treemap, Partition Map, Sunburst |
| Flow | Sankey, Chord Diagram |
| Other | Parallel Coordinates, Funnel, Gauge, Theme River, Calendar |
| Table/KPI | Table, Pivot Table, KPI, Big Number |
| 3D/WebGL | 3D Bar, 3D Surface, Scatter GL, Lines GL, Flow GL Vector Field, Graph GL, 3D Hexagon Map, 3D Geo Arcs |

---

## Data Profiling

The profiler detects:

- **Basic stats**: rows, columns, duplicates, missing values, cardinality
- **Semantic types**: `integer`, `float`, `currency`, `percentage`, `datetime`, `categorical`, `boolean`, `latitude`, `longitude`, `geo_named`, `flow_source`, `flow_target`, `identifier`, `text`
- **Dataset signals**: `has_datetime`, `has_numeric`, `has_categorical`, `has_geo_latlon`, `has_geo_named`, `has_flow`, `has_hierarchy`, `has_ohlc`

### Type Detection (5-Step Pipeline)
1. Pandas dtype
2. Column name pattern matching (regex)
3. Value sampling (first 100 values)
4. Statistical heuristics (range, cardinality, parsability)
5. Final classification

---

## Scoring Algorithm

Each chart receives a score from **0–100**:

| Factor | Max Points |
|--------|-----------|
| Required semantic types present | 30 |
| Column count satisfies min/max | 15 |
| Semantic/structural signal match | up to 40 (capped) |
| Cardinality appropriate for chart | 10 |
| Row count appropriate | 10 |

**Hard eliminators (score = 0):**
- Geographic chart without lat/lon or named geo data
- Flow chart (Sankey, Chord, Graph) without source/target columns
- OHLC chart without open/high/low/close columns
- 3D chart with fewer than 3 numeric dimensions
- Column count below chart minimum

**Soft penalties:**
- Pie/Donut: -3 per category above ideal maximum (max -40)
- WebGL charts: penalized for small datasets (<10,000 rows)

---

## Relationship Detection

Patterns detected automatically:

| Pattern | Triggers |
|---------|---------|
| `time_series` | datetime + numeric column |
| `category_metric` | categorical + numeric column |
| `two_numeric` | 2+ numeric columns |
| `three_or_more_numeric` | 3+ numeric columns |
| `multi_category_metric` | 2+ categorical + numeric |
| `hierarchical` | categorical columns with increasing cardinality |
| `flow_network` | source + target columns |
| `geo_latlon` | latitude + longitude columns |
| `geo_named_metric` | geo_named + numeric |
| `ohlc` | open + high + low + close columns |
| `single_metric` | 1 numeric, no categorical/datetime |
| `large_dataset` | >10,000 rows |

---

## How to Add a New Chart

1. Add the chart definition to `apache_echarts_chart_catalog_final.xlsx`
2. Add its metadata to `CHART_META` in `scripts/build_catalog.py`
3. Add a row in `EXCEL_CHARTS` in `scripts/build_catalog.py`
4. Run `python scripts/build_catalog.py`
5. Add column mapping logic in `scoring_engine.py → _build_mapping()`
6. Add ECharts config generation in `config_generator.py`

---

## Testing

```bash
# Run all 59 tests
cd backend
python -m pytest ../tests/ -v

# Run specific test files
python -m pytest ../tests/test_profiler.py -v
python -m pytest ../tests/test_scoring.py -v
python -m pytest ../tests/test_api.py -v
```

### Test Datasets

| Dataset | Content | Expected Top Charts |
|---------|---------|-------------------|
| `dataset1_categorical.csv` | Product + Sales | Bar, Pie |
| `dataset2_timeseries.csv` | Date + Revenue | Line, Area |
| `dataset3_numeric.csv` | Advertising + Revenue | Scatter |
| `dataset4_3d.csv` | X, Y, Z | 3D Scatter |
| `dataset5_geographic.csv` | Lat, Lon, Value | Map charts |
| `dataset6_hierarchical.csv` | Category, Subcategory, Value | Treemap, Sunburst |
| `dataset7_flow.csv` | Source, Target, Value | Sankey, Chord |
| `dataset8_large.csv` | 15,000 rows, X, Y, Category | Scatter GL |

---

## Frontend (Streamlit)

The interactive Streamlit application at `http://localhost:8501/`:
- **Live Backend Health Indicator**: Real-time status badge monitoring FastAPI at `http://localhost:8000/`
- **CSV Ingestion**: Drag-and-drop file uploader or 1-click sample dataset selection
- **Dataset Profiling Dashboard**: Rows, columns, evaluated charts count, eligible charts count, and signal chips
- **Column Semantics Inspector**: Color-coded semantic type badges, unique counts, and missing %
- **Ranked Recommendation Cards**: Ordered by score with gold/silver/bronze badges, match %, and reasons
- **Live Apache ECharts Studio**: Interactive ECharts 5.5 rendering with dark theme, tooltips, zooming, and image export
- **Interactive Column Mapping Editor**: Remap CSV columns to chart axes/roles and re-render in real time
- **ECharts Option JSON**: Formatted configuration for direct copy-pasting into production apps

---

## Environment

- Python 3.10+
- FastAPI + Uvicorn
- Pandas + NumPy + openpyxl
- Apache ECharts 5.x (CDN)
- No database required — in-memory dataset store
