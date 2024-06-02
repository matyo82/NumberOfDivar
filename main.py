from datetime import datetime
from colorama import Fore, Style
import mysql.connector
import requests
import csv

# میتونید کد شهر های بیشتری را اضافه کنید!
cities = {"1": "tehran", "2": "karaj", "3": "mashhad", "4": "esfahan", "33": "kish"}

# database
config = {
    'user': 'root',
    'password': '',
    'host': '127.0.0.1',
    'database': 'divar',
    'raise_on_warnings': True
}

connection = mysql.connector.connect(**config)
cursor = connection.cursor()

def GetUrl(Last_Post, district, city):
    url = f"https://api.divar.ir/v8/web-search/{city}/real-estate"
    json = {
        "json_schema": {
            "category": {
                "value": "real-estate"
            },
            "business-type": {
                "value": "real-estate-business"
            },
            "districts": {
                "vacancies": [
                    str(district)
                ]
            }
        },
        "last-post-date": int(Last_Post)
    }
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "Referer": "https://divar.ir/",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    res = requests.post(url, json=json, headers=headers)
    if res.status_code != 200:
        print("Link not valid.")
        pass
    data = res.json()
    last_post_date = data['last_post_date']
    list_of_tokens = []
    count = 0
    stopped = False
    while not stopped:
        json = {
            "json_schema": {
                "category": {
                    "value": "real-estate"
                },
                "business-type": {
                    "value": "real-estate-business"
                },
                "districts": {
                    "vacancies": [
                        str(district)
                    ]
                }
            },
            "last-post-date": int(last_post_date)
        }

        res = requests.post(url, json=json, headers=headers)
        print(res)
        if res.status_code != 200:
            print("Link not valid.")
            break
        data = res.json()
        last_post_date = data['last_post_date']

        for widget in data['web_widgets']['post_list']:
            token = widget['data']['token']
            last_post = widget['action_log']['server_side_info']['info']['extra_data']['last_post_sort_date']
            if district != "1":
                mahaleh = widget['action_log']['server_side_info']['info']['extra_data']["jli"]['districts'][
                    'vacancies']
            elif district == "1":
                mahaleh = ['default', 'default']
            else:
                print("کد منطقه نامعتبر است!")

            name = widget['data']['bottom_description_text']
            list_of_tokens.append(token)
            count += 1
            print(name + ' - ' + token + ' - ' + mahaleh[0])
            try:
                query = "INSERT INTO numbers (token, lastpost, name, district, city, dateAdd) VALUES (%s, %s, %s, %s, %s, %s)"
                values = (token, int(last_post), name, mahaleh[0], cities[city], datetime.now().strftime("%Y-%m-%d"))
                select_query = "SELECT COUNT(*) FROM numbers WHERE token = %s"
                cursor.execute(select_query, (token,))
                result = cursor.fetchone()
                if result[0] == 0:
                    cursor.execute(query, values)
                    connection.commit()
                else:
                    print(Fore.RED + f"Duplicate entry for {token}. Skipping to the next item." + Style.RESET_ALL)
            except mysql.connector.IntegrityError as e:
                print(f"An error occurred: {e}")
                continue

            if count >= 2000:
                print("Done.")
                try:
                    cursor.execute("""
                    DELETE numbers
                    FROM numbers
                    JOIN (
                        SELECT MIN(id) AS min_id, name
                        FROM numbers
                        GROUP BY name
                    ) AS duplicates ON numbers.id <> duplicates.min_id AND numbers.name = duplicates.name;
                    """)
                    connection.commit()
                    print("Duplicate records deleted successfully!")

                except mysql.connector.Error as err:
                    print(f"Error: {err}")
                    connection.rollback()

                finally:
                    cursor.close()
                    connection.close()
                stopped = True
                break


def GetNumber():
    query = "SELECT * FROM numbers WHERE number IS NULL OR number = ''"
    cursor.execute(query)
    records = cursor.fetchall()

    authorization = input("iter toke: ")
    headers = {
        'Host': 'api.divar.ir',
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.5",
        "Referer": "https: // divar.ir /",
        "Authorization": authorization,
        "Origin": "https: // divar.ir",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-GPC": "1",
    }
    json = ''
    sum = 0
    for record in records:
        url = f"https://api.divar.ir/v8/postcontact/web/contact_info/{record[1]}"
        res = requests.get(url, json=json, headers=headers)
        data = res.json()
        try:
            if not data['widget_list'][0]['data']['action']['payload']['phone_number']:
                number = "00000000000"
                raise ValueError("erorr nomber or link ...!")
            number = data['widget_list'][0]['data']['action']['payload']['phone_number']
        except ValueError as e:
            print(e)
        # number = data['widget_list'][0]['data']['action']['payload']['phone_number']
        print(record[1] + ' = ' + number)
        print(sum)
        update_query = "UPDATE numbers SET number = %s, dateAdd = %s WHERE id = %s"
        cursor.execute(update_query, (number, datetime.now().strftime("%Y-%m-%d"), record[0]))
        connection.commit()
        sum = sum + 1
        if sum >= 255:
            print("Done")
            break


def DeleteUrl():
    query = "SELECT * FROM numbers WHERE number IS NULL OR number = '' ORDER BY dateAdd"
    cursor.execute(query)
    records = cursor.fetchall()
    for record in records:
        url = f"https://divar.ir/v/-/{record[1]}"
        res = requests.get(url)
        print(res)
        if res.status_code == 404:
            query_delete = "DELETE FROM numbers WHERE id = %s AND token = %s"
            cursor.execute(query_delete, (record[0], record[1]))
            connection.commit()
            print(f"Delete token:{record[1]} and id: {record[0]}")
    cursor.close()
    connection.close()


def GetCsvFle(export_to_csv):
    select_query = "SELECT id, number, name, city, district FROM numbers"
    cursor.execute(select_query)
    records = cursor.fetchall()
    column_names = [i[0] for i in cursor.description]
    with open(export_to_csv, 'w', newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(column_names)
        csvwriter.writerows(records)

    print("Data exported to CSV successfully.")


while True:
    job = input("What do you want to do?\n 1)Save new addresses\n 2)Save numbers\n 3)Delete old links\n 4)Get the csv "
                "file\n 0)Exit\n")
    if job == "1":
        city = input("inter code city: ")
        district = input("inter district:")
        Last_Post = input("enter last Post: ")
        GetUrl(Last_Post=Last_Post, district=district, city=city)
        break
    elif job == "2":
        GetNumber()
        break
    elif job == "3":
        DeleteUrl()
        print("The deletion was successful!")
        break
    elif job == "0" or job == "exit" or job == "Exit":
        print("Exiting the program.")
        break
    elif job == "4":
        path = input("inter your path address: ")
        fileName = datetime.now().strftime("%Y-%m-%d") + "_numbers.csv"
        export_to_csv = path + "/" + fileName
        GetCsvFle(export_to_csv)
        break
    else:
        print("Invalid input. Please enter either 1, 2, or 'exit' to quit.")
