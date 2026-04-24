@app.route("/admin/orders/<order_id>/delete", methods=["POST"])
@admin_required
def delete_order(order_id: str):
    orders = read_orders()
    remaining = [o for o in orders if str(o.get("id")) != str(order_id)]
    if len(remaining) == len(orders):
        flash("Order not found.", "warning")
        return redirect(url_for("admin_dashboard"))
    write_orders(remaining)
    flash(f"Order {order_id} deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@user_passes_test(is_admin)
def admin_station_delete(request, station_id):



@app.route("/cart/update", methods=["POST"])
def update_cart_item():
    item_id = request.form.get("item_id")
    current_size = request.form.get("current_size", "")
    new_size = request.form.get("size", "").strip()
    quantity_raw = request.form.get("quantity", "1")
    try:
        quantity = max(0, int(quantity_raw))
    except ValueError:
        quantity = 1

    cart = get_cart()
    target_index = next((i for i, it in enumerate(cart) if it["id"] == item_id and it.get("size", "") == current_size), None)
    if target_index is None:
        flash("Item not found in cart.", "warning")
        return redirect(url_for("view_cart"))

    target = cart.pop(target_index)
    available_sizes = target.get("available_sizes", [])
    if available_sizes:
        if not new_size:
            new_size = current_size or available_sizes[0]
        if new_size not in available_sizes:
            flash("Invalid size selected.", "danger")
            cart.insert(target_index, target)
            save_cart(cart)
            return redirect(url_for("view_cart"))
    else:
        new_size = ""

    if quantity == 0:
        save_cart(cart)
        flash("Item removed from cart.", "info")
        return redirect(url_for("view_cart"))

    target["quantity"] = quantity
    target["size"] = new_size

    for item in cart:
        if item["id"] == target["id"] and item.get("size", "") == target.get("size", ""):
            item["quantity"] += target["quantity"]
            save_cart(cart)
            flash("Cart updated.", "info")
            return redirect(url_for("view_cart"))

    cart.append(target)
    save_cart(cart)
    flash("Cart updated.", "info")
    return redirect(url_for("view_cart"))




@app.route("/admin/items/<item_id>/delete", methods=["POST"])
@admin_required
def delete_item(item_id: str):
    items = read_items()
    remaining = [it for it in items if it.get("id") != item_id]
    if len(remaining) == len(items):
        flash("Item not found.", "warning")
        return redirect(url_for("admin_dashboard"))

    removed = next((it for it in items if it.get("id") == item_id), None)
    if removed and removed.get("image"):
        image_path = UPLOADS_DIR / removed["image"]
        if image_path.exists():
            image_path.unlink()

    write_items(remaining)
    flash("Item deleted.", "info")
    return redirect(url_for("admin_dashboard"))
