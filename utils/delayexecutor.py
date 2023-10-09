import schedule
import time
from datetime import datetime
from utils.logger import Logger

# Create a dictionary to store job references
scheduled_jobs = {}

def execute_at_datetime(datetime_str, task):
    def job():
        print(f"Task executed at {datetime_str}")
        task()

    target_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")

    # Calculate the delay until the target datetime
    delay = (target_datetime - datetime.now()).total_seconds()

    # Schedule the job with the calculated delay and store the job reference
    job_ref = schedule.every(int(delay)).seconds.do(job)
    scheduled_jobs[datetime_str] = job_ref

def cancel_task(datetime_str):
    # Cancel a task by its target datetime string
    if datetime_str in scheduled_jobs:
        job_ref = scheduled_jobs[datetime_str]
        job_ref.cancel()
        print(f"Task at {datetime_str} canceled.")
        del scheduled_jobs[datetime_str]
    else:
        print(f"No task found for datetime {datetime_str}.")

def setup_daily_scheduler(daily_task):
    def job():
        daily_task()
    schedule.every().day.at("00:00").do(job)

def run_scheduler():
    Logger().info(f'Scheduler start running at {datetime.now()}')
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start the scheduler
if __name__ == "__main__":
    run_scheduler()

