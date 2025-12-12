"""
Leo.py: A loop that observes, decides, and acts. A living system.

Two browser windows in playwright chromium headless browser, so login details are always retained when it logs into an account given.
Flashscore.com and Football.com 

THE BEGINNING 
1. On flashscore.com window, get to flashscore.com/football, and click on the Scheduled tab to see all upcoming leagues with their corresponding matches yet to be played on the current date.
2. Extract for each match: the match ID, the league URL, the match URL, the home team name, the away team name, the match time.
3. Sort the matches by time and visit the first match (earliest match).
4. On the match page, click the H2H tab. Using Vision, extract the match’s region_league name (e.g., England - Premier League), the match group (if there is), the home team (e.g., Chelsea) last 10 matches (e.g., Chelsea 2 vs Brighton 1 - 29.05.2025 - match URL - England - Premier League - match ID, Real Madrid 3 vs Chelsea 2 - 07.06.2025 - match URL - Europe - Champions League - match ID , etc.)
5. Repeat 4 for away team, and same for their direct H2H matches which are not more than 18 months (from the current date). 
6. Save all the data from 4 and 5 to schedules.csv file, with match ID as the unique identifier.
7. Click the standings tab or draw tab, extract all the data and the league ID and team IDs. Save to the standings.csv or draw.csv, and teams.csv.
8. Analyze and process the match and make predictions using the model.py. Save predictions to the predictions.csv.
9. Repeat steps 2 to 8 for the next match. If all scheduled matches for the current date are done, proceed to step 11.
10. In the flashscore browser window, click the next day button (call the date the target date), till you reach the target date. Repeat steps 1 to 9 for the target date. If the target date is 6 days from the current date, proceed to step 30.
11. On the football.com browser window, if the top right Login button is visible, proceed to step 12 else proceed to step 13.
12. Click the login button on the home page, and in the login page, enter the mobile number, password and click the large Login button.
13. In the home page, extract the account balance and currency.
14. Click the full schedule text button to get to the schedule page. 
15. Click “Daily” drop down and select “Today” if the predictions that are unbooked have match date and time is for current date and time (not started) proceed to step 17. Else proceed to step 16.
16. Click the day (e.g., Sunday, Monday, Tuesday etc.) from the drop down that corresponds to the target date day.
17. Click the “Sort” drop down and select “League”.
18. For each league, expand their headers (if not expanded) to reveal their matches. Extract the league URL, their match URLs, match date and time, the home and away team names.
19. Match the extracted data from step 18 with the predictions.csv matches, using Gemini to identify the predictions.csv matches in the football.com schedule matches. 
20. For each of the matches matched in step 19, visit their URL. 
21. For each match you visit, expand the market headers (if not expanded) to reveal all the available options and outputs for the given market. Extract all the markets, their options and outcomes as well as their corresponding button selector.
22. Send the extracted data above to Gemini alongside their corresponding predictions details in the predictions.csv, and request for the safest, most likely outcome that must occur. Gemini is to return the button selector for that outcome or respond with “SKIP” if no safe option is found
23. Click the selector provided by Gemini and ensure the betslip counter increases after that selector was clicked. If “SKIP”, proceed to step 24
24. Repeat steps 20 to 23 for all the matched matches. Proceed to step 25 if all matched matches have been processed.
25. Click the betslip counter to reveal the betslip bottom modal. 
26. Click “Book Bet” and extract the booking code, link and download the PNG of the betslip. Click back button when done 
27. Repeat step 25 and click the stake input field.
28. Using the onscreen keyboard, enter the stake amount and click the “Done” button.
29. Click “Place Bet” button and click “Confirm” button. Update the predictions.csv bet status. Return to step 10
30. Check the last match date in the predictions.csv, if current date is 6 days from the match date, repeat step 30 else proceed to step 10: target date is last match date in the predictions.csv +1.

LeoBook files:
1. Leo.py (AKA main.py, this very The Beginning Algorithm above). Can create and modify all these other LeoBook files, if they don't exist.
2. Sites (folder): flashscore.py, football_com.py.
3. Neo (folder): intelligence.py, model.py.
4. Helpers (folder): Neo_Helpers (folder: Managers(folder: api_key_manager, db_manager, extraction_manager, popups_manager, prolution_manager, tooltips_manager, vision_manager), Prompts(folder: each page has their prompt file)), Site_Helpers (folder: page_logger, Extractors (folder: each page has their extraction file)), Utils (folder),.
5. DB (folder): knowledge.json, schedules.csv, standings.csv, teams.csv, region_league.csv, predictions.csv, Auth (folder).
6. Logs (folder): Error (folder: page_error.html, page_error.png, resolutions.txt), Page (folder: page.html, page.png), Terminal (folder: leo_session_date_time.log)
"""