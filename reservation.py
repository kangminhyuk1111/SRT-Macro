import asyncio
from telegram import Bot
from datetime import datetime

from SRT import SRT, SeatType
token = "6059038962:AAENLGizE3JTcxg1_y_O651YZ5RbK_VkvB8"
bot = Bot(token=token)


srt = SRT("2196982283", "rkdglqkr12@") # 회원번호, 비밀번호
name = "강민혁" # 이름
dep = '동대구'  # 출발
arr = '수서'  # 도착
date = '20241229'  # 날짜 (yyyymmdd)
time = '170000'  # 시간 (HHMMSS)

trains = srt.search_train(dep, arr, date, time, available_only=False)
trains

import time
async def make_reservation():
    await bot.sendMessage(chat_id=-4032297041, text=f"{name}님이 예약을 시작하셨습니다.\n예약완료 알림을 받게되면 10분안에 반드시 결제해주셔야 합니다.")
    flag = False
    i = 0
    while flag == False:
        try:
            i += 1
            time.sleep(0.8)
            print(f"{i}번째 시도")
            reservation = srt.reserve(trains[0], special_seat=SeatType.GENERAL_ONLY)
            # 예약 정보를 문자열로 추출
            print(reservation)
            # 문자열을 Telegram으로 전송
            flag = True
            depTime = datetime.strptime(reservation.dep_time, "%H%M%S").time()
            arrTime = datetime.strptime(reservation.arr_time, "%H%M%S").time()
            paymentTime = datetime.strptime(reservation.payment_time, "%H%M%S").time()

            await bot.sendMessage(
                chat_id=-4032297041,
                text=f"@{name} 님 예약 완료 되었습니다. \n{reservation.dep_station_name} : {depTime} ~ {reservation.arr_station_name} : {arrTime} \n {paymentTime}까지 결제를 완료해주세요.")

        except Exception as e:
            print(f"예외 발생: {e}")


asyncio.run(make_reservation())