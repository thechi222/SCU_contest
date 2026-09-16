def sync_booking_tasks() -> None:
    """由 run_scheduler 每 30 秒呼叫一次,依資料庫現況補建任務,可重複執行:

      - pending 且 start_time 已到:機台為 idle 時以 enqueue_task(booking, "start") 建立任務;
        機台為 offline / busy 時將預約標為 failed
      - active 且 end_time 已到:以 enqueue_task(booking, "stop") 建立任務
      - 超過 60 秒未回報心跳的機台:標為 offline

    已開通的 session 不因機台轉為 busy 而中斷,busy 只阻擋新的開通。
    """
    ...
