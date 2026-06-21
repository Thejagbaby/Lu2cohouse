import schedule, time
from agent3_analytics import run_daily_report
from agent2_poster import post_daily_pin
from agent4_repinner import post_daily_repin

schedule.every().day.at("08:00").do(lambda: run_daily_report())
schedule.every().day.at("09:00").do(lambda: post_daily_pin())
schedule.every().day.at("11:00").do(lambda: post_daily_repin())
schedule.every().day.at("13:00").do(lambda: post_daily_pin())
schedule.every().day.at("16:00").do(lambda: post_daily_repin())
schedule.every().day.at("20:00").do(lambda: post_daily_pin())

print("LU2COHOUSE Agent System started.")
print("Own pins: 09:00 + 13:00 + 20:00 | Repins: 11:00 + 16:00 | Analytics: 08:00")
while True:
    schedule.run_pending()
    time.sleep(60)
