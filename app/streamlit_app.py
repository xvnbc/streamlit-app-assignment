"""Streamlit dashboard: operations analysis of an electric car-sharing fleet.

Run from the project root:
    uv run streamlit run app/streamlit_app.py

The data file is read from the DATA_PATH environment variable
(default: data/rentals.csv).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from assignment_streamlit_app import config as c
from assignment_streamlit_app import metrics, threshold
from assignment_streamlit_app.cleaning import build_rental_dataset
from assignment_streamlit_app.loading import load_raw_data

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = Path(os.environ.get("DATA_PATH", PROJECT_ROOT / "data" / "rentals.csv"))

TIME_BIN_MINUTES = 30

TYPE_LABELS = {
    c.CUSTOMER_RENTAL: "Customer rental",
    c.AGENT_CHARGE: "Agent charge",
    c.AGENT_MOVE: "Agent move",
}
TYPE_COLORS = {
    c.CUSTOMER_RENTAL: "#E4575B",
    c.AGENT_CHARGE: "#3B75AF",
    c.AGENT_MOVE: "#F28E2B",
}
BATTERY_VIEWS = {
    "Charging start": (c.AGENT_CHARGE, "chargelevelstart_filled"),
    "Charging end": (c.AGENT_CHARGE, "charge_level_end_fixed"),
    "Move start": (c.AGENT_MOVE, "chargelevelstart_filled"),
    "Customer rental start": (c.CUSTOMER_RENTAL, c.CHARGE_START),
}

st.set_page_config(page_title="EV Car-Sharing Operations", page_icon="🔋", layout="wide")


@st.cache_data(show_spinner="Loading and cleaning data...")
def load_events(path: str) -> pd.DataFrame:
    """Load the CSV and run the cleaning pipeline."""
    return build_rental_dataset(load_raw_data(path))


@st.cache_data
def load_snapshots(events: pd.DataFrame) -> pd.DataFrame:
    return threshold.build_charge_snapshots(events)


def dual_axis_chart(df: pd.DataFrame, x: str, title: str) -> go.Figure:
    """Bars for rental counts, line for total rented hours."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=df[x], y=df["rentals"], name="Rentals", marker_color="#3B75AF")
    fig.add_scatter(
        x=df[x],
        y=df["total_duration_min"] / 60,
        name="Rented hours",
        mode="lines+markers",
        line_color="#F28E2B",
        secondary_y=True,
    )
    fig.update_yaxes(title_text="Rentals", secondary_y=False)
    fig.update_yaxes(title_text="Rented hours", secondary_y=True, showgrid=False)
    fig.update_layout(title=title, legend={"orientation": "h", "y": 1.1},
                      margin={"t": 70})
    return fig


# --------------------------------------------------------------------------- data
if not DATA_PATH.exists():
    st.error(
        f"No data found at `{DATA_PATH}`. Add the file there "
        "or set the `DATA_PATH` environment variable."
    )
    st.stop()

events = load_events(str(DATA_PATH))
snapshots = load_snapshots(events)

# --------------------------------------------------------------------------- layout
st.title("🔋 Electric car-sharing operations")
tab_overview, tab_demand, tab_daily, tab_charging, tab_threshold = st.tabs(
    ["Overview", "Demand", "Daily pattern", "Charging & moves", "Battery threshold"]
)

# --- Overview ---------------------------------------------------------------------
with tab_overview:
    st.markdown(
        "This dashboard analyses one year of anonymised events from an urban electric "
        "car-sharing service (mobility sector). Each row is either a **customer rental** "
        "or a **service operation** performed by an agent: charging a car or moving it "
        "off a charging station."
    )

    summary = metrics.utilization_summary(events)
    cols = st.columns(4)
    cols[0].metric("Vehicles", summary.n_vehicles)
    cols[1].metric("Rentals per vehicle per day",
                   f"{summary.rentals_per_vehicle_per_day:.1f}")
    cols[2].metric("Average rental", f"{summary.avg_duration_min:.0f} min")
    cols[3].metric(
        "Utilization rate",
        f"{summary.utilization_rate:.1%}",
        help="Total customer rental time / (vehicles × hours in the period)",
    )
    st.caption(
        f"{summary.n_rentals:,} customer rentals from {summary.start_date:%d %b %Y} "
        f"to {summary.end_date:%d %b %Y} ({summary.n_days} days)."
    )

    left, right = st.columns(2)
    counts = metrics.event_type_counts(events)
    counts["label"] = counts["rental_type"].map(TYPE_LABELS)
    left.plotly_chart(
        px.pie(
            counts,
            names="label",
            values="count",
            color="rental_type",
            color_discrete_map=TYPE_COLORS,
            title="Events by type",
            hole=0.4,
        )
    )
    per_vehicle = metrics.rentals_per_vehicle(events, summary.n_days)
    right.plotly_chart(
        px.histogram(
            per_vehicle,
            x="rentals_per_day",
            nbins=20,
            title="Rentals per day, distribution across vehicles",
            labels={"rentals_per_day": "Rentals per day"},
        ).update_layout(yaxis_title="Vehicles")
    )

# --- Demand -----------------------------------------------------------------------
with tab_demand:
    monthly = metrics.monthly_demand(events)
    st.plotly_chart(dual_axis_chart(monthly, "month", "Monthly demand"))
    st.caption("The first and last months of the dataset are partial.")
    weekly = metrics.weekday_demand(events)
    st.plotly_chart(dual_axis_chart(weekly, "weekday", "Demand by day of week"))

# --- Daily pattern ----------------------------------------------------------------
with tab_daily:
    shown_types = st.multiselect(
        "Event types",
        c.RENTAL_TYPES,
        default=c.RENTAL_TYPES,
        format_func=TYPE_LABELS.get,
    )
    if not shown_types:
        st.info("Select at least one event type.")
    else:
        profile = metrics.hourly_profile(events, TIME_BIN_MINUTES)
        profile = profile[profile["rental_type"].isin(shown_types)]
        profile["type"] = profile["rental_type"].map(TYPE_LABELS)
        fig = px.bar(
            profile,
            x="hour",
            y="count",
            color="rental_type",
            color_discrete_map=TYPE_COLORS,
            facet_row="type",
            labels={"hour": "Time of day (h)", "count": "Events"},
            height=250 * len(shown_types),
        )
        fig.update_yaxes(matches=None)  # each event type keeps its own scale
        fig.update_layout(showlegend=False, bargap=0.05)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig)
        st.caption(
            "Customers peak at commuting hours, while agents mostly work 8am–3pm. "
            "Shifting part of the service work to early morning or evening would "
            "reduce overlap with customer demand."
        )

# --- Charging & moves -------------------------------------------------------------
with tab_charging:
    charging = metrics.charging_summary(events)
    cols = st.columns(3)
    cols[0].metric("Charging sessions", f"{charging.n_sessions:,}")
    cols[1].metric("Sessions ending at 100 %", f"{charging.full_ratio:.0%}")
    cols[2].metric(
        "Average charging speed",
        f"{charging.avg_rate_pct_per_min:.2f} %/min",
        help="Computed on sessions ending below 100 %.",
    )

    views = st.multiselect(
        "Battery level at...",
        list(BATTERY_VIEWS),
        default=["Charging start", "Charging end", "Move start"],
    )
    chart_cols = st.columns(2)
    for i, view in enumerate(views):
        rental_type, column = BATTERY_VIEWS[view]
        dist = metrics.battery_distribution(events, rental_type, column)
        fig = px.bar(
            dist,
            x="battery_bin",
            y="share",
            title=view,
            color_discrete_sequence=[TYPE_COLORS[rental_type]],
            labels={"battery_bin": "Battery level (%)", "share": "Share of events"},
        )
        fig.update_yaxes(tickformat=".0%")
        chart_cols[i % 2].plotly_chart(fig)

# --- Battery threshold ------------------------------------------------------------
with tab_threshold:
    st.markdown(
        "**Question:** while a car is charging, it may be rented before it is full. "
        "Above which battery level is this unlikely enough to send an agent to "
        "move it off the charger?"
    )
    c1, c2 = st.columns(2)
    window = c1.slider("Window after charging (min)", 15,
                       180, c.DEFAULT_WINDOW_MINUTES, 15)
    min_events = c2.number_input(
        "Hide battery levels with fewer sessions than",
        min_value=1,
        value=5,
        step=1,
        help="Battery levels with few charging sessions give very noisy probabilities.",
    )

    prob = threshold.rental_probability_by_soc(snapshots, window)
    prob = prob[prob["n_events"] >= min_events]
    if prob.empty:
        st.info("No battery level has enough sessions. Lower the minimum.")
    else:
        chosen = st.slider("Candidate threshold (%)", 50, 100, 90, 5)
        fig = px.line(
            prob,
            x="soc_bin",
            y="prob_rented",
            markers=True,
            hover_data={"n_events": True},
            labels={
                "soc_bin": "Battery level at end of charge (%)",
                "prob_rented": "Probability next event is a rental",
                "n_events": "Sessions",
            },
            title=f"Rental probability within {window} min after charging",
        )
        fig.add_vline(x=chosen, line_dash="dash", line_color="#E4575B")
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(fig)

        within = snapshots[snapshots["time_to_next_min"] <= window]
        above = within[within["soc"] >= chosen]
        m1, m2 = st.columns(2)
        m1.metric(
            f"Rental probability at ≥ {chosen} %",
            f"{above['label_rented'].mean():.0%}" if len(above) else "n/a",
        )
        m2.metric("Sessions at or above threshold", f"{len(above):,}")
        st.caption(
            "Only charging sessions followed by another event within the window "
            "are counted: the curve reads as *given the car is used again soon, "
            "how often is it by a customer?*"
        )

        with st.expander("Data behind the chart"):
            st.dataframe(prob, hide_index=True)
