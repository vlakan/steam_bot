import psycopg2
from config import host, user, password, db_name

# If you want to delete table items - uncomment and run this code ->
# connection = psycopg2.connect(
#   host=host,
#   user=user,
#   password=password,
#   database=db_name
# )
# connection.autocommit = True
# with connection.cursor() as cursor:
#   cursor.execute("""DROP TABLE IF EXISTS items""")
# connection.close()


def sql_calling(func):
    def wrapper(*args, **kwargs):
        conn = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            database=db_name
        )
        cur = conn.cursor()

        result = func(cur=cur, *args, **kwargs)

        conn.commit()
        cur.close()
        conn.close()
        return result
    return wrapper


@sql_calling
def clean_sql_states(cur):
    cur.execute("""DROP TABLE IF EXISTS states""")


@sql_calling
def start_sql(cur):
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS items
                    (id serial PRIMARY KEY,
                    skin_name varchar(100),
                    sticker_name varchar(200),
                    skin_price REAL,
                    skin_quantity INTEGER,
                    skin_url varchar(500)
                    );""")
        print('Database items connected OK!')

        cur.execute("""CREATE TABLE IF NOT EXISTS states
                    (proxy varchar(25),
                    login varchar(25)
                    );""")
        print('Database states connected OK!')
    except Exception as ex:
        print('[INFO] Error while start PostgreSQL', ex)


@sql_calling
def sql_add_item_command(data, have, cur):
    if have:
        cur.execute(f"UPDATE items SET skin_price = '{data[2]}', skin_quantity='{data[3]}', skin_url='{data[4]}'"
                    f" WHERE skin_name = '{data[0]}' AND sticker_name = '{data[1]}'")
    else:
        cur.execute(f"INSERT INTO items (skin_name, sticker_name, skin_price, skin_quantity, skin_url)"
                    f" VALUES ('{data[0]}', '{data[1]}', '{data[2]}', '{data[3]}', '{data[4]}')")


@sql_calling
def sql_check_for_new_item(name, sticker, cur):
    cur.execute(f"SELECT * FROM items WHERE skin_name = '{name}' AND sticker_name = '{sticker}'")
    result = cur.fetchone()
    if result:
        cur.execute(f"SELECT skin_quantity, skin_price FROM items WHERE skin_name = '{name}' AND sticker_name = '{sticker}'")
        return cur.fetchone()
    else:
        return False


@sql_calling
def not_check_in(value, cur):
    cur.execute(f"SELECT * FROM states WHERE proxy='{value}'")
    result = cur.fetchone()
    if result:
        return False
    else:
        return True


@sql_calling
def insert(value, cur):
    cur.execute(f"INSERT INTO states (proxy) VALUES ('{value}')")


@sql_calling
def not_check_in_log(value, cur):
    cur.execute(f"SELECT * FROM states WHERE login ='{value}'")
    result = cur.fetchone()
    if result:
        return False
    else:
        return True


@sql_calling
def insert_log(value, value2, cur):
    cur.execute(f"UPDATE states SET login = '{value}' WHERE proxy = '{value2}'")


@sql_calling
def delete(value, cur):
    cur.execute(f"DELETE FROM states WHERE proxy='{value}'")
