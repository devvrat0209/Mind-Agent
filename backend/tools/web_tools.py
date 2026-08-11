import requests
import datetime

def search_web(query: str, num_results: int = 5):
    """Mock web search - in production would call SerpAPI/Bing etc
    For now returns structured query to be handled by LLM or external fetcher
    """
    # Try to use DuckDuckGo instant answer as free fallback
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=5
        )
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data.get("AbstractText"),
                "url": data.get("AbstractURL", "")
            })
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("Text","")[:80],
                    "snippet": topic.get("Text",""),
                    "url": topic.get("FirstURL","")
                })
        if results:
            return {"query": query, "results": results[:num_results]}
    except Exception as e:
        pass
    
    # Fallback mock
    return {
        "query": query,
        "results": [
            {
                "title": f"Search result for '{query}'",
                "snippet": "Web search requires API key. Configure SERPAPI_KEY or use local browsing. For demo, I'm providing contextual answer.",
                "url": "https://duckduckgo.com/?q=" + query.replace(" ", "+")
            }
        ],
        "note": "Configure external search API for full results"
    }

def get_weather(location: str = "auto"):
    """Get weather using open-meteo (free, no key)"""
    try:
        # Geocode location
        if location.lower() in ["auto", "here", "current"]:
            # Use IP geolocation fallback
            geo_resp = requests.get("https://ipapi.co/json/", timeout=5).json()
            lat = geo_resp.get("latitude", 37.7749)
            lon = geo_resp.get("longitude", -122.4194)
            city = geo_resp.get("city", "San Francisco")
        else:
            # Geocode via open-meteo geocoding
            geo_resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1},
                timeout=5
            ).json()
            if not geo_resp.get("results"):
                return {"error": f"Location not found: {location}"}
            first = geo_resp["results"][0]
            lat = first["latitude"]
            lon = first["longitude"]
            city = first["name"]

        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto"
            },
            timeout=5
        ).json()

        current = weather_resp.get("current_weather", {})
        daily = weather_resp.get("daily", {})
        
        return {
            "location": city,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": current.get("temperature"),
            "temperature_f": round(current.get("temperature", 0) * 9/5 + 32, 1) if current.get("temperature") else None,
            "wind_speed": current.get("windspeed"),
            "weather_code": current.get("weathercode"),
            "time": current.get("time"),
            "forecast": {
                "dates": daily.get("time", [])[:3],
                "max": daily.get("temperature_2m_max", [])[:3],
                "min": daily.get("temperature_2m_min", [])[:3],
            }
        }
    except Exception as e:
        return {"error": f"Weather fetch failed: {str(e)}", "location": location}

def fetch_url_content(url: str):
    """Fetch a URL and extract text"""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "JARVIS-Agent/1.0"})
        # Truncate
        text = resp.text[:8000]
        return {"url": url, "status": resp.status_code, "content_preview": text}
    except Exception as e:
        return {"error": str(e), "url": url}
