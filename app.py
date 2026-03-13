import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Tankerkönig Finder", page_icon="⛽", layout="wide")

API_KEY = st.secrets.get("TANKERKOENIG_API_KEY", os.getenv("TANKERKOENIG_API_KEY", ""))

TANKERKOENIG_URL = "https://creativecommons.tankerkoenig.de/json/list.php"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "streamlit-tankerkoenig-app/1.0"
}


def geocode_location(mode: str, value: str, country: str = "Germany"):

    params = {
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 1,
        "countrycodes": "de",
    }

    if mode == "City":
        params["city"] = value
        params["country"] = country
    else:
        params["postalcode"] = value
        params["country"] = country

    response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()

    results = response.json()

    if not results:
        return None

    result = results[0]

    return {
        "lat": float(result["lat"]),
        "lng": float(result["lon"]),
        "display_name": result.get("display_name", value),
    }


def get_stations(lat: float, lng: float, radius: float, fuel_type: str):

    params = {
        "lat": lat,
        "lng": lng,
        "rad": radius,
        "type": fuel_type,
        "apikey": API_KEY,
        "sort": "dist",
    }

    response = requests.get(TANKERKOENIG_URL, params=params, timeout=20)
    response.raise_for_status()

    return response.json()


def build_dataframe(stations: list, fuel_type: str):

    rows = []

    for station in stations:

        row = {
            "Name": station.get("name"),
            "Brand": station.get("brand"),
            "Street": station.get("street"),
            "House Number": station.get("houseNumber"),
            "Postal Code": station.get("postCode"),
            "City": station.get("place"),
            "Distance (km)": station.get("dist"),
            "Open": station.get("isOpen"),
            "Latitude": station.get("lat"),
            "Longitude": station.get("lng"),
        }

        if fuel_type == "all":
            row["Diesel (€)"] = station.get("diesel")
            row["Super E5 (€)"] = station.get("e5")
            row["Super E10 (€)"] = station.get("e10")
        else:
            row["Price (€)"] = station.get("price")

        rows.append(row)

    df = pd.DataFrame(rows)

    return df


st.title("⛽ Tankerkönig Fuel Station Finder")
st.caption("Find fuel stations in Germany by city or postal code.")

if not API_KEY:
    st.error(
        "No API key found. Please add TANKERKOENIG_API_KEY to `.streamlit/secrets.toml`."
    )
    st.stop()


with st.sidebar:

    st.header("Search options")

    search_mode = st.radio("Search by", ["City", "Postal Code"], horizontal=True)

    if search_mode == "City":
        location_value = st.text_input("City", value="Berlin")
    else:
        location_value = st.text_input("Postal Code", value="10115")

    radius = st.slider("Radius (km)", min_value=1, max_value=50, value=10)

    fuel_display = {
        "Diesel": "diesel",
        "Super E5": "e5",
        "Super E10": "e10",
        "All Fuel Types": "all"
    }

    fuel_type_label = st.selectbox("Fuel Type", list(fuel_display.keys()))
    fuel_type = fuel_display[fuel_type_label]

    sort_option = st.selectbox(
        "Sort Results By",
        ["Price", "Distance", "Station Name"]
    )

    search_clicked = st.button("Search Stations", type="primary", use_container_width=True)


if search_clicked:

    if not location_value.strip():
        st.warning("Please enter a city or postal code.")
        st.stop()

    try:

        with st.spinner("Resolving location..."):
            location = geocode_location(search_mode, location_value.strip())

        if not location:
            st.error("Location not found.")
            st.stop()

        st.success(f"Location found: {location['display_name']}")

        with st.spinner("Fetching stations..."):
            data = get_stations(
                lat=location["lat"],
                lng=location["lng"],
                radius=radius,
                fuel_type=fuel_type,
            )

        if not data.get("ok"):
            st.error(f"API error: {data.get('message')}")
            st.stop()

        stations = data.get("stations", [])

        if not stations:
            st.info("No stations found.")
            st.stop()

        df = build_dataframe(stations, fuel_type)

        if sort_option == "Price" and "Price (€)" in df.columns:
            df = df.sort_values(by="Price (€)")

        elif sort_option == "Distance":
            df = df.sort_values(by="Distance (km)")

        elif sort_option == "Station Name":
            df = df.sort_values(by="Name")

        c1, c2, c3 = st.columns(3)

        c1.metric("Stations Found", len(df))
        c2.metric("Search Radius", f"{radius} km")
        c3.metric("Fuel Type", fuel_type_label)

        st.subheader("Stations")

        # hide coordinates in table
        table_df = df.drop(columns=["Latitude", "Longitude"])

        st.dataframe(table_df, use_container_width=True)

        st.subheader("Map")

        st.map(
            df.rename(columns={"Latitude": "lat", "Longitude": "lon"})[
                ["lat", "lon"]
            ]
        )

        csv = table_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Results as CSV",
            data=csv,
            file_name="tankerkonig_stations.csv",
            mime="text/csv",
        )

    except requests.HTTPError as e:
        st.error(f"HTTP error: {e}")

    except requests.RequestException as e:
        st.error(f"Request failed: {e}")

    except Exception as e:
        st.error(f"Unexpected error: {e}")

else:

    st.info("Select your filters in the sidebar and click **Search Stations**.")