import flet as ft
import flet.fastapi as flet_fastapi
from db_helpers import add_new_phone, search_phone, sell_phone_db, return_phone_db, get_monthly_report, get_connection, start_sync_thread

SECRET_PIN = "kk1102" # كلمة السر لحماية الشاشات الحساسة

def main(page: ft.Page):
    # إعدادات الشاشة للموبايل (تصميم أبيض عصري)
    page.title = "نظام إدارة المحل"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F8F9FA"
    page.padding = 0
    page.rtl = True

    # بدء تشغيل المزامنة الخفية للسحاب
    start_sync_thread()

    # رأس الصفحة
    status_text = ft.Text("جاري الفحص...", size=12, color=ft.colors.GREY_700)
    page.appbar = ft.AppBar(
        title=ft.Text("إدارة الهواتف", weight=ft.FontWeight.BOLD, color="#1E293B"),
        bgcolor=ft.colors.WHITE,
        elevation=0.5,
        actions=[ft.Container(content=status_text, padding=ft.padding.only(left=15))]
    )

    # حوار التأكيد بكلمة السر
    def ask_password(on_success):
        pin_input = ft.TextField(label="كلمة السر", password=True, can_reveal_password=True, autofocus=True)
        def confirm(e):
            if pin_input.value == SECRET_PIN:
                page.dialog.open = False
                page.update()
                on_success()
            else:
                pin_input.error_text = "كلمة السر خاطئة!"
                page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("إجراء محمي بكلمة سر"),
            content=pin_input,
            actions=[
                ft.TextButton("إلغاء", on_click=lambda e: setattr(page.dialog, 'open', False) or page.update()),
                ft.ElevatedButton("تأكيد", bgcolor="#2563EB", color=ft.colors.WHITE, on_click=confirm)
            ]
        )
        page.dialog = dialog
        dialog.open = True
        page.update()

    # 1. واجهة الإدخال الشراء
    def view_add():
        brand = ft.TextField(label="النوع*", hint_text="مثال: Samsung", border_radius=10)
        model = ft.TextField(label="الموديل*", hint_text="مثال: A54", border_radius=10)
        storage = ft.TextField(label="المساحة*", hint_text="مثال: 128GB", border_radius=10)
        buy_price = ft.TextField(label="سعر الشراء*", keyboard_type=ft.KeyboardType.NUMBER, border_radius=10, prefix_text="EGP ")
        
        battery = ft.TextField(label="نسبة البطارية %", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        acc = ft.TextField(label="الملحقات", border_radius=8)
        ram = ft.TextField(label="الرامات", border_radius=8)
        notes = ft.TextField(label="ملاحظات", multiline=True, border_radius=8)

        def save_click(e):
            if not brand.value or not model.value or not storage.value or not buy_price.value:
                page.show_snack_bar(ft.SnackBar(ft.Text("من فضلك اكمل الحقول الأساسية!")))
                return
            
            data = {
                'brand': brand.value, 'model': model.value, 'storage': storage.value,
                'buy_price': float(buy_price.value), 'battery_health': int(battery.value) if battery.value else None,
                'accessories': acc.value, 'ram': ram.value, 'notes': notes.value
            }
            ok, msg = add_new_phone(data)
            page.show_snack_bar(ft.SnackBar(ft.Text(msg)))
            if ok:
                brand.value = model.value = storage.value = buy_price.value = battery.value = acc.value = ram.value = notes.value = ""
                page.update()

        return ft.ListView(
            padding=20, spacing=15,
            controls=[
                ft.Text("إضافة هاتف جديد", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    bgcolor=ft.colors.WHITE, padding=20, border_radius=16,
                    shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.BLACK12),
                    content=ft.Column([brand, model, storage, buy_price], spacing=12)
                ),
                ft.ExpansionTile(
                    title=ft.Text("تفاصيل اختيارية", size=14),
                    controls=[ft.Container(bgcolor=ft.colors.WHITE, padding=15, border_radius=12, content=ft.Column([battery, acc, ram, notes], spacing=10))]
                ),
                ft.ElevatedButton("حفظ الهاتف", bgcolor="#2563EB", color=ft.colors.WHITE, style=ft.ButtonStyle(padding=18, shape=ft.RoundedRectangleBorder(radius=12)), on_click=save_click)
            ]
        )

    # 2. واجهة البحث والبيع
    def view_search():
        search_input = ft.TextField(hint_text="ابحث برقم ID أو الموديل...", prefix_icon=ft.icons.SEARCH, border_radius=12, bgcolor=ft.colors.WHITE)
        results_col = ft.Column(spacing=10)

        def do_search(e):
            results_col.controls.clear()
            items = search_phone(search_input.value)
            for item in items:
                status_color = "#10B981" if not item['sold'] else "#EF4444"
                status_lbl = "متاح" if not item['sold'] else "مباع"
                
                card = ft.Container(
                    bgcolor=ft.colors.WHITE, padding=15, border_radius=16, shadow=ft.BoxShadow(blur_radius=8, color=ft.colors.BLACK12),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"جهاز #{item['id']}", weight=ft.FontWeight.BOLD, color="#2563EB"),
                            ft.Container(content=ft.Text(status_lbl, color=status_color, size=12, weight=ft.FontWeight.BOLD), bgcolor="#F3F4F6", padding=5, border_radius=6)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"{item['brand']} {item['model']} - {item['storage']}", size=15, weight=ft.FontWeight.W_500),
                        ft.Text(f"سعر الشراء: {item['buy_price']} ج.م", color=ft.colors.GREY_700),
                        ft.Divider(),
                        ft.Row([
                            ft.ElevatedButton("بيع الجهاز", bgcolor="#10B981", color=ft.colors.WHITE, visible=not item['sold'],
                                              on_click=lambda e, pid=item['id']: show_sell_dialog(pid)),
                            ft.ElevatedButton("مرتجع", bgcolor="#EF4444", color=ft.colors.WHITE, visible=item['sold'],
                                              on_click=lambda e, pid=item['id']: ask_password(lambda: do_return(pid)))
                        ])
                    ])
                )
                results_col.controls.append(card)
            page.update()

        search_input.on_change = do_search

        def show_sell_dialog(phone_id):
            s_price = ft.TextField(label="سعر البيع*", keyboard_type=ft.KeyboardType.NUMBER)
            c_name = ft.TextField(label="اسم العميل*")
            c_phone = ft.TextField(label="رقم التليفون")
            
            def confirm_sell(e):
                if not s_price.value or not c_name.value: return
                ok, msg = sell_phone_db(phone_id, float(s_price.value), c_name.value, c_phone.value, "")
                page.dialog.open = False
                page.show_snack_bar(ft.SnackBar(ft.Text(msg)))
                do_search(None)

            page.dialog = ft.AlertDialog(title=ft.Text(f"تسجيل بيع جهاز #{phone_id}"), content=ft.Column([s_price, c_name, c_phone], compact=True), actions=[ft.ElevatedButton("تم البيع", on_click=confirm_sell)])
            page.dialog.open = True
            page.update()

        def do_return(phone_id):
            ok, msg = return_phone_db(phone_id)
            page.show_snack_bar(ft.SnackBar(ft.Text(msg)))
            do_search(None)

        return ft.ListView(padding=20, spacing=15, controls=[search_input, results_col])

    # التنقل السفلي
    body = ft.Container(content=view_add(), expand=True)
    def nav_change(e):
        idx = e.control.selected_index
        if idx == 0: body.content = view_add()
        elif idx == 1: body.content = view_search()
        elif idx == 3: ask_password(lambda: setattr(body, 'content', ft.Text("شاشة التقارير والأرباح")) or page.update())
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0, bgcolor=ft.colors.WHITE, on_change=nav_change,
        destinations=[
            ft.NavigationDestination(icon=ft.icons.ADD_CELL_PHONE, label="إضافة"),
            ft.NavigationDestination(icon=ft.icons.SEARCH, label="استعلام/بيع"),
            ft.NavigationDestination(icon=ft.icons.INVENTORY_2, label="المتاح"),
            ft.NavigationDestination(icon=ft.icons.BAR_CHART, label="التقارير"),
        ]
    )

    page.add(body)
    _, conn_name = get_connection()
    status_text.value = f"الشبكة: {conn_name}"
    page.update()

if __name__ == "__main__":
    app = flet_fastapi.app(main)
