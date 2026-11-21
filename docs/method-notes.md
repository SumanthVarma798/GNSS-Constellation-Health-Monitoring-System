# The team's original notes on the method

Moved here unchanged from `README.md` on 12 Nov 2026, so the README can stay a short guide to using
the project. They were written for the team's earlier app (`app.py`). The dashboard (`dashboard.py`)
uses the same analysis modules in `analysis/` and the same detection thresholds. These notes were not
re-checked against the code in the move, so where they and the code disagree, the code is right.

## 🔧 Module Descriptions

### `config/config.py`
- Centralized configuration and constants
- Satellite NORAD IDs for NavIC, QZSS, BeiDou-3
- Geographic points for DOP analysis (India, Japan, China)
- Service requirements and tolerances
- Default analysis parameters
- DOP quality thresholds

### `api/`
**spacetrack_api.py**: Space-Track.org API integration
- `get_spacetrack_session()`: Authentication
- `fetch_tle_json_cached()`: Cached GP history data
- `fetch_multiple_tles()`: Latest TLE data
- `fetch_and_classify_satellite()`: Complete satellite data processing

**celestrak_api.py**: CelesTrak API integration for backup TLE data

### `analysis/`
**health_assessment.py**: Comprehensive satellite health scoring
- `assess_satellite_health_with_drift()`: Complete health assessment
- `analyze_maneuver_pattern()`: Dynamic pattern-based maneuver analysis
- Integrates inclination, maintenance, drift, longitude deviation, and uniformity

**drift_analysis.py**: Longitudinal drift calculations
- `calculate_longitudinal_drift()`: Mean motion to drift conversion
- `assess_drift_health()`: Drift-based health assessment
- `calculate_drift_trend()`: Drift trend analysis over time
- `get_drift_direction()`: Drift direction with emojis

**maneuver_detection.py**: Statistical orbital maneuver detection
- `detect_navik_maneuvers()`: Main detection algorithm
- `calculate_maneuver_uniformity()`: Spacing analysis
- MAD (Median Absolute Deviation) z-score method

**dop_calculations.py**: DOP calculations and satellite positioning
- `parse_tle_data()`: Parse TLE into satellite objects
- `calculate_satellite_position()`: Position calculations
- `calculate_dop_for_location()`: Location-specific DOP
- `calculate_bounding_boxes()`: Ground track bounding boxes
- `get_dop_quality()`: DOP quality assessment

### `visualizations/`
**visualization.py**: All plotting and visualization functions
- `plot_individual_satellites()`: Individual satellite plots
- `plot_combined_drift()`: Combined drift comparison
- `plot_bounding_boxes()`: Ground track visualizations
- `plot_sky_plot()`: Azimuth-elevation sky plots
- `plot_dop_over_time()`: DOP time series
- `plot_mean_longitude_map()`: Geographic longitude deviation map
- `plot_drift_distribution()`: Drift distribution analysis
- And more specialized plotting functions

### `app.py`
Main Streamlit application providing:
- User interface and sidebar configuration
- Data fetching and processing orchestration
- Results display and visualization coordination
- Session state management
- Longitude deviation calculation using satellite propagation

## 📊 What the Application Does

### Health Assessment
- **5-Component Scoring System**: Comprehensive 0-100 health score
  - Inclination Control (30%): Target deviation monitoring
  - Maintenance Pattern (25%): E-W and N-S maneuver analysis
  - Drift Analysis (20%): Longitudinal drift assessment
  - Longitude Deviation (15%): Slot position accuracy
  - Uniformity (10%): Maneuver spacing regularity

### Orbital Analysis
- **Longitudinal Drift**: Degrees per day calculation
- **Drift Direction**: Eastward/Westward identification
- **Altitude Monitoring**: Semi-major axis tracking
- **Inclination Trends**: Change detection over time
- **Graveyard Orbit Detection**: Decommissioned satellite identification

### Longitude Slot Deviation
**NEW FEATURE**: Monitors satellite position relative to designated orbital slots
- Uses Skyfield propagation for accurate position calculation
- Computes circular mean longitude over 24 hours
- Calculates angular deviation with wrap-around handling
- Color-coded deviation table:
  - 🟢 Green: ≤ 0.5° (Good)
  - 🟡 Yellow: 0.5° - 1.0° (Acceptable)
  - 🔴 Red: > 1.0° (Needs Attention)

### DOP Analysis
- **GDOP**: Geometric Dilution of Precision
- **PDOP**: Position Dilution of Precision
- **HDOP**: Horizontal Dilution of Precision
- **VDOP**: Vertical Dilution of Precision
- **TDOP**: Time Dilution of Precision
- **Regional Coverage**: Location-specific calculations

### Visualizations
- Individual satellite time-series plots
- Combined constellation comparison
- Sky plots (azimuth-elevation diagrams)
- Geographic longitude deviation map with designated slots
- Ground track bounding boxes
- DOP time-series (30 days)
- Drift distribution analysis

## 🎯 Health Scoring System

### Component Weights

| Component | Weight | GEO Tolerance | IGSO Tolerance |
|-----------|--------|---------------|----------------|
| **Inclination** | 30% | ± 1.0° | ± 4.0° |
| **Maintenance** | 25% | Pattern-based | Pattern-based |
| **Drift** | 20% | < 0.05°/day | < 2.0°/day |
| **Longitude Deviation** | 15% | < 0.5° | < 5.0° |
| **Uniformity** | 10% | CoV < 0.8 | CoV < 0.8 |

### Health Status Indicators

| Status | Score Range | Color | Meaning |
|--------|-------------|-------|---------|
| 🟢 Excellent | 85-100 | Green | All parameters within ideal range |
| 🟡 Good | 70-84 | Yellow | Within operational tolerance |
| 🟠 Fair | 50-69 | Orange | Some parameters degraded, monitoring needed |
| 🔴 Needs Attention | 0-49 | Red | Significant deviations, corrective action required |

## 📈 Understanding the Output

### Key Metrics Explained

**Inclination Deviation**:
- **Excellent**: < 0.3 × tolerance
- **Good**: < tolerance
- **Poor**: > tolerance

**Longitudinal Drift** (GEO):
- **Excellent**: < 0.015°/day
- **Good**: < 0.05°/day
- **Fair**: 0.05° - 0.10°/day
- **Poor**: > 0.10°/day

**Longitude Slot Deviation** (GEO):
- **Excellent**: ≤ 0.5°
- **Good**: 0.5° - 1.0°
- **Needs Attention**: > 1.0°

**Maneuvers per Month**:
- **Typical**: 1-8 maneuvers
- **Insufficient**: < 1
- **Excessive**: > 8

**DOP Values**:
- **Ideal**: < 1
- **Excellent**: 1-2
- **Good**: 2-5
- **Moderate**: 5-10
- **Fair**: 10-20
- **Poor**: > 20

## 🔧 Configuration & Customization

### Supported Constellations

| Constellation | Satellites | Coverage | Status |
|---------------|------------|----------|--------|
| **NavIC (IRNSS)** | 9 tracked; IRNSS-1A and NVS-02 left out on purpose (`registry/left_out.csv`) | India & surrounding | ✅ Fully configured |
| **QZSS (Michibiki)** | 6 (3 IGSO, 3 GEO incl. QZS-7); QZS-1 left out on purpose | Japan & Asia-Pacific | ✅ Fully configured |
| **BeiDou GEO/IGSO** (page "BeiDou-3") | 10 (4 GEO, 3 BeiDou-3 IGSO, 2 BeiDou-2 IGSO, 1 BeiDou-3 test IGSO) | Asia-Pacific | ✅ Fully configured |
| **BeiDou-3 MEO** | 30 (28 MEO, 2 test MEO) | Global | ✅ Judged by orbital plane |

`registry/dashboard_satellites.csv` is the list itself; `tests/test_registry_coverage.py` keeps every broadcasting
satellite tracked or explained.

### NavIC Orbital Slots
- **GEO**: 32.5°E, 83°E, 131.5°E (inclination ~5°)
- **GEO**: 55°E (2 sats), 111.75°E (2 sats) (inclination ~29-30°)

### Analysis Parameters

Customizable through sidebar:

**Maneuver Detection:**
- Z-Score Threshold (default: 3.5)
- SMA Change (km): 0.5
- Inclination Change (°): 0.01
- Persistence Window: 2

**Health Assessment:**
- Inclination Tolerance (°): 1.0 (NavIC), 4.0 (QZSS IGSO)
- GEO Drift Tolerance (°/day): 0.05
- Min/Max Maneuvers/Month: 1-8
- Uniformity Threshold: 0.8

**DOP Settings:**
- Elevation Mask: 0-30° (default: 5°)
- Custom location option
- Timestep: 15 minutes

## 🐛 Troubleshooting

### Common Issues

**"Failed to fetch TLE data"**
- Verify Space-Track credentials
- Check internet connection
- Ensure NORAD IDs are valid in `config/config.py`

**"No satellites parsed"**
- Check NORAD IDs are set (not `None`)
- For BeiDou-3, run `tests/find_beidou_norad_ids.py` first

**"Module not found" errors**
- Ensure all files are in correct directory structure
- Verify dependencies: `pip list`
- Check import paths use new structure

**Slow performance**
- Reduce date range
- Enable "One TLE per day" option
- Close other Streamlit instances

**Longitude deviation shows "N/A"**
- Run DOP Analysis first to create satellite objects
- Ensure constellation is selected correctly
- Check designated longitude values in config

## 🎓 Technical Background

### Algorithms

**Drift Calculation**: Based on mean motion deviation from geosynchronous rate (1.00273790935 rev/day)

**Longitude Deviation**: 
- Uses Skyfield satellite propagation
- Calculates circular mean over 24 hours
- Accounts for ±180° wrap-around
- Compares to designated slot from config

**Maneuver Detection**: MAD z-score method with persistence filtering

**Health Scoring**: Multi-factor weighted system with dynamic pattern recognition

**DOP Calculation**: Standard geometric dilution using satellite-observer geometry

### Data Sources
- **Primary**: Space-Track.org (GP history, TLE data)
- **Backup**: CelesTrak (public TLE data)
- **Calculations**: Skyfield library for precise positioning

### Performance
- Analysis time: 30-60 seconds for 9 months
- Memory usage: ~500MB for full constellation
- Supports concurrent satellite analysis

