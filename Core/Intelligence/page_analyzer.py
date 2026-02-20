# page_analyzer.py: page_analyzer.py: Webpage structure analysis and context validation.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: PageAnalyzer

"""
Page Analyzer Module
Handles webpage content analysis, data extraction, and league information processing.
Responsible for extracting structured data from web pages for prediction analysis.
"""

from typing import Dict, Any, List, Optional

from .selector_db import knowledge_db


class PageAnalyzer:
    """Handles webpage content analysis and data extraction"""

    # --- NEW: Context Validation Rules ---
    # Defines how to identify if we are on a specific page context via URL, Title, or Elements
    EXPECTED_CONTEXTS = {
        "fb_login_page": {
            "url_patterns": ["/ng/"], 
            "title_patterns": ["Login", "Sign In"],
            "identifying_selectors": ["input[type='tel']", "input[type='password']"], 
            "description": "Football.com Login Page"
        },
        "fb_match_page": {
            "url_patterns": ["/sr:match:"],
            "title_patterns": [" vs "],
            "description": "Football.com Match/Event Detail Page"
        },
        "fb_schedule_page": {
            "url_patterns": ["/sport/football/"],
            "title_patterns": ["Betting", "Odds", "Schedule"],
            "description": "Football.com Schedule/Listing Page"
        },
        "fb_main_page": {
            "url_patterns": ["football.com/ng/"],
            "title_patterns": ["Football.com"],
            # Home page shouldn't have login inputs visible usually
            "description": "Football.com Main Mobile Hub"
        },
        "fb_global": {
            "url_patterns": ["football.com"],
            "description": "Any page on Football.com (Global elements)"
        }
    }


    @staticmethod
    async def verify_page_context(page, context_key: str) -> bool:
        """
        Validates if the current browser page matches the requested context
        using URL, Title, and Identifying Selectors.
        """
        if context_key not in PageAnalyzer.EXPECTED_CONTEXTS:
            return True
            
        try:
            url = page.url.lower()
            title = (await page.title()).lower()
            rules = PageAnalyzer.EXPECTED_CONTEXTS[context_key]
            
            # 1. URL Check (Strict for match/schedule, loose for home/login)
            url_match = any(p.lower() in url for p in rules["url_patterns"])
            
            # 2. Title Check
            title_match = any(p.lower() in title for p in rules["title_patterns"])

            # 3. Identifying Selector Check (Crucial for Home vs Login)
            if "identifying_selectors" in rules:
                selector_found = False
                for sel in rules["identifying_selectors"]:
                    try:
                        # Short timeout to avoid blocking
                        if await page.locator(sel).count() > 0:
                            selector_found = True
                            break
                    except:
                        continue
                
                # For login page, we MUST see the inputs if we're at the root URL
                if context_key == "fb_login_page" and not selector_found:
                    return False
            
            if url_match or title_match:
                return True
                
            return False
        except Exception:
            return True

    @staticmethod
    async def identify_context(page) -> tuple[str, bool]:
        """
        Auto-detects page context. Returns (context_key, is_uncertain).
        """
        for context_key in PageAnalyzer.EXPECTED_CONTEXTS:
            if await PageAnalyzer.verify_page_context(page, context_key):
                return context_key, False
        
        # --- PHASE 0: VISUAL PROBE (ESCALATED AWARENESS) ---
        print("    [Phase 0] Standard discovery failed. Triggering Visual Probe...")
        return await PageAnalyzer.visual_probe_context(page)

    @staticmethod
    async def visual_probe_context(page) -> tuple[str, bool]:
        """
        Multimodal context identification with confidence retry logic.
        Returns (context_key, is_uncertain).
        V5: Retries once if confidence < 0.8 before defaulting to fb_global.
        """
        try:
            from .api_manager import gemini_api_call_with_rotation
            from .utils import clean_json_response
            
            screenshot_path = "Config/temp_probe.png"
            await page.screenshot(path=screenshot_path)
            
            with open(screenshot_path, "rb") as f:
                image_data = {"mime_type": "image/png", "data": f.read()}

            title = await page.title()
            
            # V5: Attempt 1 - Standard probe
            prompt_v1 = f"""
            Identify the functional context of this web page.
            Page Title: {title}
            URL: {page.url}
            
            List of valid context keys: {list(PageAnalyzer.EXPECTED_CONTEXTS.keys())}
            
            Return ONLY a JSON object:
            {{
                "context_key": "selected_key",
                "confidence_score": 0.0 to 1.0,
                "reasoning": "Brief explanation"
            }}
            """
            
            response = await gemini_api_call_with_rotation([prompt_v1, image_data])
            data = json.loads(clean_json_response(response.text))
            
            ctx = data.get("context_key", "fb_global")
            conf = data.get("confidence_score", 1.0)
            
            # V5: Retry logic for low confidence
            if conf < 0.8:
                print(f"    [Phase 0 RETRY] Initial confidence {conf} too low. Retrying with focused prompt...")
                
                prompt_v2 = f"""
                RETRY: The previous attempt had low confidence. Focus on PRIMARY NAVIGATION elements and CORE PAGE STRUCTURE.
                
                Page Title: {title}
                URL: {page.url}
                
                Valid context keys: {list(PageAnalyzer.EXPECTED_CONTEXTS.keys())}
                
                Look for:
                - Login/Logout buttons → likely fb_login_page or fb_home_page
                - Match listings → likely fb_schedule_page
                - Single match details → likely fb_match_page
                
                Return ONLY JSON:
                {{
                    "context_key": "selected_key",
                    "confidence_score": 0.0 to 1.0,
                    "reasoning": "Specific UI element that confirmed this"
                }}
                """
                
                retry_response = await gemini_api_call_with_rotation([prompt_v2, image_data])
                retry_data = json.loads(clean_json_response(retry_response.text))
                
                ctx_retry = retry_data.get("context_key", "fb_global")
                conf_retry = retry_data.get("confidence_score", 0.0)
                
                print(f"    [Phase 0 RETRY] Retry confidence: {conf_retry}, Context: {ctx_retry}")
                
                # Use retry result if it improved confidence
                if conf_retry >= conf:
                    ctx = ctx_retry
                    conf = conf_retry
            
            is_uncertain = conf < 0.8
            if is_uncertain:
                print(f"    [Phase 0 WARNING] Final confidence ({conf}) still low for '{ctx}'. Flagging as UNCERTAIN.")
                
            return ctx, is_uncertain
            
        except Exception as e:
            print(f"    [Visual Probe Error] Failed to classify state: {e}")
            return "fb_global", True

    @staticmethod
    async def discover_state_via_ai(page) -> Dict[str, Any]:
        """
        Autonomous State Discovery.
        Used when the system is on an unknown page or modal.
        Uses Leo AI to analyze HTML content to determine context and next steps.
        """
        from .prompts import STATE_DISCOVERY_PROMPT
        from .api_manager import grok_api_call

        print("    [SMART NAV] Unrecognized page state. Triggering Leo AI Discovery...")

        try:
            # 1. Extract HTML content (focus on visible, interactive elements)
            html_content = await page.evaluate("""
                () => {
                    // Get key structural elements
                    const getVisibleText = (element) => {
                        if (!element) return '';
                        const style = window.getComputedStyle(element);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                            return '';
                        }
                        return element.textContent.trim().substring(0, 200); // Limit text length
                    };

                    const extractElement = (selector, label) => {
                        const el = document.querySelector(selector);
                        return el ? `${label}: "${getVisibleText(el)}"` : '';
                    };

                    // Collect key page information
                    const pageInfo = [];

                    // Page title and URL
                    pageInfo.push(`PAGE_TITLE: "${document.title}"`);
                    pageInfo.push(`PAGE_URL: "${window.location.href}"`);

                    // Common interactive elements
                    const selectors = [
                        ['h1', 'MAIN_HEADING'],
                        ['h2', 'SUB_HEADING'],
                        ['[role="dialog"]', 'MODAL_DIALOG'],
                        ['.modal, .popup, .overlay', 'MODAL_OVERLAY'],
                        ['form', 'FORM_ELEMENT'],
                        ['input[type="text"], input[type="email"], input[type="tel"]', 'TEXT_INPUT'],
                        ['input[type="password"]', 'PASSWORD_INPUT'],
                        ['button', 'BUTTONS'],
                        ['a[href]', 'LINKS'],
                        ['[data-testid*="login"], [class*="login"]', 'LOGIN_ELEMENT'],
                        ['[data-testid*="search"], [class*="search"]', 'SEARCH_ELEMENT'],
                        ['[data-testid*="menu"], .menu, nav', 'NAVIGATION'],
                        ['.error, .alert, [role="alert"]', 'ERROR_MESSAGE'],
                        ['.loading, .spinner', 'LOADING_INDICATOR']
                    ];

                    selectors.forEach(([sel, label]) => {
                        const elements = document.querySelectorAll(sel);
                        if (elements.length > 0) {
                            const texts = Array.from(elements).map(getVisibleText).filter(t => t);
                            if (texts.length > 0) {
                                pageInfo.push(`${label}: ${texts.slice(0, 3).join(' | ')}`);
                            }
                        }
                    });

                    // Body text sample (first meaningful paragraph)
                    const bodyText = document.body.textContent.trim().substring(0, 500);
                    pageInfo.push(`BODY_SAMPLE: "${bodyText}"`);

                    return pageInfo.filter(item => item.includes(': "') && item.split(': "')[1].length > 1).join('\\n');
                }
            """)

            # 2. Format prompt with HTML content
            formatted_prompt = STATE_DISCOVERY_PROMPT.format(html_content=html_content)

            # 3. Ask Leo AI for analysis
            response = await grok_api_call(
                formatted_prompt,
                generation_config={"response_mime_type": "application/json"}
            )

            if response and hasattr(response, 'text') and response.text:
                import json
                from .utils import clean_json_response

                cleaned = clean_json_response(response.text)
                data = json.loads(cleaned)

                print(f"    [SMART NAV] Leo AI identifies state: {data.get('state')} | Milestone: {data.get('milestone_found')}")
                return data

        except Exception as e:
            print(f"    [SMART NAV ERROR] AI state discovery failed: {e}")

        return {"state": "unknown", "is_modal": False}

    @staticmethod
    async def extract_league_data(
        page, context_key: str = "home_page"
    ) -> Dict[str, List[str]]:
        """Extract league and match data from webpage"""
        selectors = knowledge_db.get(context_key, {})
        if not selectors:
            return {"leagues": []}

        required = ["sport_container", "league_header", "match_rows"]
        if not all(k in selectors for k in required):
            return {"leagues": []}

        try:
            data = await page.evaluate(
                """(selectors) => {
                const container = document.querySelector(selectors.sport_container);
                if (!container) return { leagues: [] };

                const results = [];
                let currentLeagueStr = "";
                let currentMatches = [];

                const getText = (parent, sel) => {
                    if (!sel) return "";
                    const el = parent.querySelector(sel);
                    return el ? el.innerText.trim() : "";
                };

                const flushCurrentLeague = () => {
                    if (currentLeagueStr) {
                        const fullString = currentLeagueStr + (currentMatches.length ? ', ' + currentMatches.join(', ') : '');
                        results.push(fullString);
                    }
                };

                const children = Array.from(container.children);
                const flushCurrentLeague = () => {
                    if (currentLeagueStr) {
                        const fullString = currentLeagueStr + (currentMatches.length ? ', ' + currentMatches.join(', ') : '');
                        results.push(fullString);
                    }
                };

                children.forEach(el => {
                    let header = null;
                    if (el.matches(selectors.league_header)) header = el;
                    else if (el.querySelector(selectors.league_header)) header = el.querySelector(selectors.league_header);

                    if (header) {
                        flushCurrentLeague();
                        const country = getText(header, selectors.league_category) || "Unknown";
                        const name = getText(header, selectors.league_title_link) || "League";
                        const linkEl = header.querySelector(selectors.league_title_link);
                        const href = linkEl ? linkEl.href : "";

                        currentLeagueStr = `${country}: ${name}, ${href}`;
                        currentMatches = [];
                    }
                    else if (el.matches(selectors.match_rows)) {
                        if (currentLeagueStr) {
                            const linkEl = selectors.event_row_link ?
                                       el.querySelector(selectors.event_row_link) :
                                       el.querySelector('a');
                            if (linkEl && linkEl.href) currentMatches.push(linkEl.href);
                        }
                    }
                });

                flushCurrentLeague();
                return { leagues: results };
            }""",
                selectors,
            )

            return data

        except Exception as e:
            print(f"    [EXTRACT ERROR] Failed to extract data: {e}")
            return {"leagues": []}

    @staticmethod
    async def get_league_url(page) -> str:
        """Extract league URL from match page"""
        try:
            # Look for breadcrumb links to league
            league_link_sel = "a[href*='/football/'][href$='/']"
            league_link = page.locator(league_link_sel).first
            href = await league_link.get_attribute('href', timeout=2000)
            if href:
                return href
        except:
            pass
        return ""

    @staticmethod
    async def get_final_score(page) -> str:
        """Extract final score from match page"""
        try:
            # Import here to avoid circular imports
            from .selector_manager import SelectorManager

            # Check Status
            status_selector = await SelectorManager.get_selector_auto(page, "match_page", "meta_match_status")
            if not status_selector:
                status_selector = "div.fixedHeaderDuel__detailStatus"

            try:
                status_text = await page.locator(status_selector).inner_text(timeout=3000)
            except:
                status_text = "finished"

            if "finished" not in status_text.lower() and "aet" not in status_text.lower() and "pen" not in status_text.lower():
                return "NOT_FINISHED"

            # Extract Score
            home_score_sel = await SelectorManager.get_selector_auto(page, "match_page", "header_score_home")
            if not home_score_sel:
                home_score_sel = "div.detailScore__wrapper > span:nth-child(1)"

            away_score_sel = await SelectorManager.get_selector_auto(page, "match_page", "header_score_away")
            if not away_score_sel:
                away_score_sel = "div.detailScore__wrapper > span:nth-child(3)"

            home_score = await page.locator(home_score_sel).first.inner_text(timeout=2000)
            away_score = await page.locator(away_score_sel).first.inner_text(timeout=2000)

            final_score = f"{home_score.strip() if home_score else ''}-{away_score.strip() if away_score else ''}"
            return final_score

        except Exception as e:
            print(f"    [SCORE ERROR] Failed to extract score: {e}")
            return "Error"

    @staticmethod
    async def extract_match_metadata(page, context: str = "match_page") -> Dict[str, Any]:
        """Extract comprehensive match metadata"""
        metadata = {}

        try:
            # Import here to avoid circular imports
            from .selector_manager import SelectorManager

            # Extract basic match info
            selectors_to_try = {
                "home_team": "header_home_name",
                "away_team": "header_away_name",
                "match_time": "meta_match_time",
                "match_status": "meta_match_status",
                "league_country": "meta_breadcrumb_country",
                "league_name": "meta_breadcrumb_league"
            }

            for field, selector_key in selectors_to_try.items():
                selector = await SelectorManager.get_selector_auto(page, context, selector_key)
                if selector:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0:
                            text = await element.inner_text(timeout=2000)
                            metadata[field] = text.strip()
                    except:
                        pass

            # Extract score if match is finished
            if metadata.get("match_status", "").lower() == "finished":
                score = await PageAnalyzer.get_final_score(page)
                if score not in ["Error", "NOT_FINISHED"]:
                    metadata["final_score"] = score

        except Exception as e:
            print(f"    [METADATA ERROR] Failed to extract match metadata: {e}")

        return metadata

    @staticmethod
    async def analyze_page_structure(page, context: str = "generic") -> Dict[str, Any]:
        """Analyze overall page structure and identify key elements"""
        structure = {
            "has_navigation": False,
            "has_content": False,
            "has_forms": False,
            "has_buttons": False,
            "has_links": False,
            "estimated_content_size": 0
        }

        try:
            # Quick structural analysis
            nav_count = await page.locator("nav, [role='navigation'], .nav, .navbar").count()
            structure["has_navigation"] = nav_count > 0

            content_count = await page.locator("main, .content, .main, article, section").count()
            structure["has_content"] = content_count > 0

            form_count = await page.locator("form").count()
            structure["has_forms"] = form_count > 0

            button_count = await page.locator("button").count()
            structure["has_buttons"] = button_count > 0

            link_count = await page.locator("a").count()
            structure["has_links"] = link_count > 0

            # Estimate content size
            body_text = await page.locator("body").inner_text()
            structure["estimated_content_size"] = len(body_text) if body_text else 0

        except Exception as e:
            print(f"    [STRUCTURE ERROR] Failed to analyze page structure: {e}")

        return structure
