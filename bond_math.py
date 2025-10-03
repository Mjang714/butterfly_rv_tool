def calculate_bond_price(years_to_maturity, yield_to_maturity, coupon_rate, frequency=2, face_value=100)->float:
    periodic_coupon_payment = (face_value * coupon_rate) / frequency
    periodic_yield = yield_to_maturity / frequency
    total_payments = years_to_maturity * frequency

    bond_price = 0
    for i in range(1, total_payments + 1):
        bond_price += periodic_coupon_payment / (1 + periodic_yield)**i
    bond_price += face_value / (1 + periodic_yield)**total_payments
    return bond_price

def macaulay_duration(face_value, coupon_rate, yield_to_maturity, years_to_maturity, frequency=1):
    """
    Computes the Macaulay Duration of a bond.

    Args:
        face_value (float): The face value (par value) of the bond.
        coupon_rate (float): The annual coupon rate as a decimal (e.g., 0.05 for 5%).
        yield_to_maturity (float): The annual yield to maturity as a decimal.
        years_to_maturity (int): The number of years until the bond matures.
        frequency (int): The number of coupon payments per year (e.g., 1 for annual, 2 for semi-annual).

    Returns:
        float: The Macaulay Duration of the bond.
    """
    if frequency <= 0:
        raise ValueError("Frequency must be a positive integer.")

    coupon_payment = (face_value * coupon_rate) / frequency
    periods = years_to_maturity * frequency
    discounted_cash_flows_weighted = 0
    bond_price = 0

    for t in range(1, periods + 1):
        # Calculate the cash flow for the current period
        cash_flow = coupon_payment
        if t == periods:  # Add face value at maturity
            cash_flow += face_value

        # Calculate the present value of the cash flow
        discount_factor = (1 + yield_to_maturity / frequency) ** t
        present_value_cash_flow = cash_flow / discount_factor

        # Accumulate for bond price calculation
        bond_price += present_value_cash_flow

        # Accumulate for duration calculation (time-weighted present value)
        discounted_cash_flows_weighted += (t / frequency) * present_value_cash_flow

    if bond_price == 0:
        raise ValueError("Bond price is zero, cannot calculate duration.")

    macaulay_duration_value = discounted_cash_flows_weighted / bond_price
    return macaulay_duration_value