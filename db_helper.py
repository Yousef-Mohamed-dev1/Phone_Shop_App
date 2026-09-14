import psycopg2
from psycopg2.extras import RealDictCursor
import threading
import time

# --- رابط قاعدة البيانات المحلية والجلوبال ---
# استبدل الباسورد والـ IP ببياناتك الحقيقية
LOCAL_DB_URI = "postgresql://postgres:yousef1312012@192.168.0.102:5432/phone_shop"
CLOUD_DB_URI = "postgresql://postgres:Yousef1312012*@db.ywbcmahdcrxhezewjzty.supabase.co:5432/postgres"

# --- 1. فحص نوع الاتصال المتاح (لوكال أم جلوبال) ---
def get_connection():
    """يفحص الواي فاي المحلي أولاً، وإذا لم يجده يتحول لـ Supabase أونلاين"""
    try:
        conn = psycopg2.connect(LOCAL_DB_URI, connect_timeout=1)
        return conn, "لوكال (الواي فاي)"
    except Exception:
        try:
            conn = psycopg2.connect(CLOUD_DB_URI, connect_timeout=4)
            return conn, "سحابي (Supabase)"
        except Exception:
            return None, "غير متصل"

# --- 2. إضافة جهاز جديد ---
def add_new_phone(data):
    conn, _ = get_connection()
    if not conn: return False, "تعذر الاتصال بقواعد البيانات!"
    try:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO phones (brand, model, storage, buy_price, battery_health, accessories, ram, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """
            cur.execute(sql, (
                data['brand'], data['model'], data['storage'], data['buy_price'],
                data.get('battery_health'), data.get('accessories'), data.get('ram'), data.get('notes')
            ))
            new_id = cur.fetchone()[0]
            conn.commit()
            return True, f"تم التسجيل بنجاح! رقم الجهاز هو #{new_id}"
    except Exception as e:
        return False, f"حدث خطأ: {str(e)}"
    finally:
        conn.close()

# --- 3. البحث والاستعلام عن جهاز ---
def search_phone(query):
    conn, _ = get_connection()
    if not conn: return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if query.isdigit():
                cur.execute("SELECT * FROM phones WHERE id = %s;", (int(query),))
            else:
                cur.execute("SELECT * FROM phones WHERE brand ILIKE %s OR model ILIKE %s ORDER BY id DESC LIMIT 20;", (f"%{query}%", f"%{query}%"))
            return cur.fetchall()
    finally:
        conn.close()

# --- 4. تسجيل عملية بيع وحساب الربح تلقائياً ---
def sell_phone_db(phone_id, sell_price, customer_name, customer_phone, sell_notes):
    conn, _ = get_connection()
    if not conn: return False, "تعذر الاتصال!"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT buy_price FROM phones WHERE id = %s AND sold = FALSE;", (phone_id,))
            res = cur.fetchone()
            if not res: return False, "الجهاز مباع بالفعل أو غير موجود!"
            
            profit = float(sell_price) - float(res['buy_price'])

            sql = """
            UPDATE phones 
            SET sold = TRUE, sell_price = %s, sell_date = CURRENT_TIMESTAMP,
                customer_name = %s, customer_phone = %s, sell_notes = %s,
                profit = %s, is_synced = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """
            cur.execute(sql, (sell_price, customer_name, customer_phone, sell_notes, profit, phone_id))
            conn.commit()
            return True, f"تم البيع! صافي الربح: {profit:,.2f} ج.م"
    finally:
        conn.close()

# --- 5. تسجيل مرتجع وإعادة الجهاز للمتاح ---
def return_phone_db(phone_id):
    conn, _ = get_connection()
    if not conn: return False, "تعذر الاتصال!"
    try:
        with conn.cursor() as cur:
            sql = """
            UPDATE phones 
            SET sold = FALSE, sell_price = NULL, sell_date = NULL,
                customer_name = NULL, customer_phone = NULL, sell_notes = NULL,
                profit = NULL, is_synced = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """
            cur.execute(sql, (phone_id,))
            conn.commit()
            return True, "تم إرجاع الجهاز لقائمة المتاح!"
    finally:
        conn.close()

# --- 6. تقرير أرباح الشهور ---
def get_monthly_report(year, month):
    conn, _ = get_connection()
    if not conn: return {'total_sales': 0, 'total_profit': 0, 'items': []}
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
            SELECT * FROM phones 
            WHERE sold = TRUE AND EXTRACT(YEAR FROM sell_date) = %s AND EXTRACT(MONTH FROM sell_date) = %s
            ORDER BY sell_date DESC;
            """
            cur.execute(sql, (year, month))
            items = cur.fetchall()
            return {
                'total_sales': sum(i['sell_price'] for i in items if i['sell_price']),
                'total_profit': sum(i['profit'] for i in items if i['profit']),
                'items': items
            }
    finally:
        conn.close()

# --- 7. محرك المزامنة التلقائي للسحاب (Background Sync Worker) ---
def start_sync_thread():
    def sync_loop():
        while True:
            try:
                l_conn = psycopg2.connect(LOCAL_DB_URI, connect_timeout=2)
                c_conn = psycopg2.connect(CLOUD_DB_URI, connect_timeout=4)
                
                with l_conn.cursor(cursor_factory=RealDictCursor) as l_cur:
                    l_cur.execute("SELECT * FROM phones WHERE is_synced = FALSE;")
                    unsynced = l_cur.fetchall()
                    
                    if unsynced:
                        with c_conn.cursor() as c_cur:
                            for item in unsynced:
                                sql = """
                                INSERT INTO phones (sync_id, id, brand, model, storage, buy_price, buy_date, battery_health, accessories, ram, notes, sold, sell_price, sell_date, customer_name, customer_phone, sell_notes, profit, is_synced, updated_at)
                                VALUES (%(sync_id)s, %(id)s, %(brand)s, %(model)s, %(storage)s, %(buy_price)s, %(buy_date)s, %(battery_health)s, %(accessories)s, %(ram)s, %(notes)s, %(sold)s, %(sell_price)s, %(sell_date)s, %(customer_name)s, %(customer_phone)s, %(sell_notes)s, %(profit)s, TRUE, %(updated_at)s)
                                ON CONFLICT (sync_id) DO UPDATE SET sold=EXCLUDED.sold, sell_price=EXCLUDED.sell_price, sell_date=EXCLUDED.sell_date, customer_name=EXCLUDED.customer_name, profit=EXCLUDED.profit, is_synced=TRUE, updated_at=EXCLUDED.updated_at;
                                """
                                c_cur.execute(sql, item)
                            c_conn.commit()
                        
                        ids = [i['sync_id'] for i in unsynced]
                        l_cur.execute("UPDATE phones SET is_synced = TRUE WHERE sync_id = ANY(%s);", (ids,))
                        l_conn.commit()
                l_conn.close()
                c_conn.close()
            except Exception:
                pass
            time.sleep(15) # يفحص ويرفع البيانات كل 15 ثانية تلقائياً

    t = threading.Thread(target=sync_loop, daemon=True)
    t.start()