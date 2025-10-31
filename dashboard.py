import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Crypto Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for better aesthetics
st.markdown("""
<style>
    .stMetric {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stMetric label {
        font-size: 14px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 Live Crypto & DeFi Dashboard")

# ---------- CONFIG ----------
col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    if st.button("🔄 Refresh Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

with col2:
    min_apy = st.number_input("Min APY Filter (%)", min_value=0, max_value=100, value=10, step=5)

with col3:
    st.markdown(f"**Last Updated:** {datetime.now():%Y-%m-%d %H:%M:%S}")

# ---------- HELPERS ----------
@st.cache_data(ttl=60, show_spinner=False)
def _fetch(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"⚠️ API request failed: {url}")
        return {}

def fmt_b(x): 
    if x >= 1e9:
        return f"${x/1e9:.1f}B"
    elif x >= 1e6:
        return f"${x/1e6:.1f}M"
    else:
        return f"${x:,.0f}"

def fmt_large(x):
    if x >= 1e9:
        return f"{x/1e9:.2f}B"
    elif x >= 1e6:
        return f"{x/1e6:.2f}M"
    else:
        return f"{x:,.0f}"

# ---------- DATA ----------
with st.spinner("📊 Fetching fresh data…"):
    # Protocols
    raw = _fetch("https://api.llama.fi/protocols")
    if raw:
        protocols = pd.DataFrame(raw)
        protocols['tvl'] = pd.to_numeric(protocols.get('tvl', 0), errors='coerce').fillna(0)
        protocols['change_1d'] = pd.to_numeric(protocols.get('change_1d', 0), errors='coerce').fillna(0)
        protocols = protocols.sort_values('tvl', ascending=False).head(10)
    else:
        protocols = pd.DataFrame()

    # Chains
    raw = _fetch("https://api.llama.fi/chains")
    if raw:
        chains = pd.DataFrame(raw)
        chains['tvl'] = pd.to_numeric(chains.get('tvl', 0), errors='coerce').fillna(0)
        chains = chains.sort_values('tvl', ascending=False).head(10)
    else:
        chains = pd.DataFrame()

    # Stablecoins
    raw = _fetch("https://stablecoins.llama.fi/stablecoins")
    if raw and 'peggedAssets' in raw:
        assets = raw.get('peggedAssets', [])
        stables = pd.DataFrame(assets)
        def usd(x):
            return x.get('peggedUSD', 0) if isinstance(x, dict) else 0
        stables['circulating_usd'] = stables['circulating'].apply(usd)
        stables = stables.sort_values('circulating_usd', ascending=False).head(6)
    else:
        stables = pd.DataFrame()

    # Yields
    raw = _fetch("https://yields.llama.fi/pools")
    if raw and 'data' in raw:
        yields = pd.DataFrame(raw.get('data', []))
        if not yields.empty:
            yields['apy'] = pd.to_numeric(yields.get('apy', 0), errors='coerce').fillna(0)
            yields['tvlUsd'] = pd.to_numeric(yields.get('tvlUsd', 0), errors='coerce').fillna(0)
            yields = yields[yields['apy'].gt(min_apy) & yields['apy'].lt(1000)]
            yields = yields.sort_values('apy', ascending=False).head(12)
    else:
        yields = pd.DataFrame()

    # Prices with 24h change
    prices = _fetch(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            'ids': 'bitcoin,ethereum,solana,cardano,polkadot,avalanche-2,chainlink,polygon',
            'vs_currencies': 'usd',
            'include_24hr_change': 'true'
        }
    )

# ---------- PRICE METRICS ----------
st.subheader("💰 Top Cryptocurrencies")

price_coins = [
    ('bitcoin', 'Bitcoin', '₿'),
    ('ethereum', 'Ethereum', 'Ξ'),
    ('solana', 'Solana', 'SOL'),
    ('cardano', 'Cardano', 'ADA'),
    ('polkadot', 'Polkadot', 'DOT'),
    ('avalanche-2', 'Avalanche', 'AVAX'),
    ('chainlink', 'Chainlink', 'LINK'),
    ('polygon', 'Polygon', 'MATIC'),
]

cols = st.columns(4)
for idx, (coin_id, name, symbol) in enumerate(price_coins):
    with cols[idx % 4]:
        coin_data = prices.get(coin_id, {})
        price = coin_data.get('usd', 0)
        change = coin_data.get('usd_24h_change', 0)
        
        if price > 0:
            st.metric(
                f"{symbol} {name}",
                f"${price:,.2f}" if price < 1000 else f"${price:,.0f}",
                f"{change:+.2f}%",
                delta_color="normal"
            )
        else:
            st.metric(f"{symbol} {name}", "N/A", "0.00%")

st.markdown("---")

# ---------- CHARTS ----------
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Top 10 DeFi Protocols by TVL")
    if not protocols.empty:
        fig = px.bar(
            protocols, 
            x='name', 
            y='tvl', 
            color='category',
            labels={'tvl': 'TVL (USD)', 'name': 'Protocol'},
            text=protocols['tvl'].apply(fmt_b),
            hover_data={'tvl': ':,.0f', 'change_1d': ':.2f'}
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            height=500, 
            showlegend=True,
            xaxis_tickangle=45,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📊 View Raw Data"):
            display_df = protocols[['name', 'category', 'tvl', 'change_1d']].copy()
            display_df['tvl'] = display_df['tvl'].apply(lambda x: f"${x:,.0f}")
            display_df['change_1d'] = display_df['change_1d'].apply(lambda x: f"{x:.2f}%")
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Protocol data unavailable")

with col2:
    st.subheader("⛓️ Top 10 Blockchains by TVL")
    if not chains.empty:
        fig = px.bar(
            chains, 
            x='name', 
            y='tvl',
            labels={'tvl': 'TVL (USD)', 'name': 'Chain'},
            color='name', 
            text=chains['tvl'].apply(fmt_b),
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig.update_traces(textposition='outside', showlegend=False)
        fig.update_layout(height=500, xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📊 View Raw Data"):
            display_df = chains[['name', 'tvl']].copy()
            display_df['tvl'] = display_df['tvl'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Chain data unavailable")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("💵 Top Stablecoins by Market Cap")
    if not stables.empty:
        fig = px.pie(
            stables, 
            names='symbol', 
            values='circulating_usd',
            color_discrete_sequence=px.colors.sequential.Viridis,
            hole=0.4
        )
        fig.update_traces(
            textinfo='percent+label',
            textposition='auto',
            hovertemplate='<b>%{label}</b><br>Market Cap: $%{value:,.0f}<extra></extra>'
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📊 View Raw Data"):
            display_df = stables[['name', 'symbol', 'circulating_usd']].copy()
            display_df['circulating_usd'] = display_df['circulating_usd'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info("Stablecoin data unavailable")

with col2:
    st.subheader(f"🌾 High-Yield Pools (>{min_apy}% APY)")
    if not yields.empty:
        # Limit to top 10 for better display
        yields_display = yields.head(10)
        fig = px.bar(
            yields_display, 
            y='symbol', 
            x='apy', 
            orientation='h',
            labels={'apy': 'APY (%)', 'symbol': 'Pool'},
            color='chain',
            text=yields_display['apy'],
            hover_data={'project': True, 'tvlUsd': ':,.0f', 'apy': ':.2f'}
        )
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📊 View Raw Data"):
            display_df = yields[['symbol', 'project', 'chain', 'apy', 'tvlUsd']].copy()
            display_df['apy'] = display_df['apy'].apply(lambda x: f"{x:.2f}%")
            display_df['tvlUsd'] = display_df['tvlUsd'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info(f"No pools found with APY > {min_apy}%")

# ---------- SUMMARY STATS ----------
st.markdown("---")
st.subheader("📊 Market Summary")

sum_cols = st.columns(4)
with sum_cols[0]:
    total_defi_tvl = protocols['tvl'].sum() if not protocols.empty else 0
    st.metric("Total DeFi TVL (Top 10)", fmt_b(total_defi_tvl))

with sum_cols[1]:
    total_chain_tvl = chains['tvl'].sum() if not chains.empty else 0
    st.metric("Total Chain TVL (Top 10)", fmt_b(total_chain_tvl))

with sum_cols[2]:
    total_stable_cap = stables['circulating_usd'].sum() if not stables.empty else 0
    st.metric("Stablecoin Market Cap", fmt_b(total_stable_cap))

with sum_cols[3]:
    avg_apy = yields['apy'].mean() if not yields.empty else 0
    st.metric("Avg High-Yield APY", f"{avg_apy:.1f}%")

st.markdown("---")
st.caption("📡 Data Sources: DeFiLlama, CoinGecko | Built with Streamlit | Updates every 60 seconds")
st.caption("⚠️ DISCLAIMER: This dashboard is for informational purposes only. Not financial advice. DYOR.")