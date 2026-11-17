"""Links to the operator status pages shown on the constellation overviews."""

# The constellations whose overview carries an official operator status page. GLONASS and BeiDou
# are deliberately absent: there is no single stable operator page we can point to today.
OFFICIAL_STATUS_URLS = {
    "Galileo": "https://www.gsc-europa.eu/system-service-status/constellation-information",
    "GPS": "https://www.navcen.uscg.gov/gps-constellation",
    "QZSS": "https://sys.qzss.go.jp/dod/en/constellation.html",
    "NavIC": "https://www.isro.gov.in/IRNSS_Programme.html",
}
