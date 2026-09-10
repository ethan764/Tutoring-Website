import stripe
import os

stripe.api_key = os.environ.get("STRIPE_API_KEY")

hour_credit_product_id = "prod_VBgX7NNBinixKI"
price_id_dict = {
    "39 one-time" : "price_1UBJAR1vEDu20daPCDHQzR4N",
    "39 weekly" : "price_1UBJBi1vEDu20daPmnYfC1gh", # do this later
    "35 one-time" : "price_1UBJBi1vEDu20daP870eaiR9",
    "35 weekly" : "price_1UBJBi1vEDu20daPIVkJ0UXO" # do this later
}

def create_customer(student_name, email):
    customer = stripe.Customer.create(
        name=student_name,
        email=email
    )
    return customer

def find_subscriptions(customer_id):
    subscriptions = stripe.Subscription.list(
        customer=customer_id,
        status="active"
    )

    return subscriptions

# cancels all of a customer's subscriptions immediately
def cancel_subscriptions(customer_id):
    subscriptions = find_subscriptions(customer_id)
    for subscription in subscriptions:
        stripe.Subscription.delete(subscription.id)

def create_checkout_session(customer_id, price_type, quantity, success_url, cancel_url):
    session = stripe.checkout.Session.create(
        customer=customer_id,
        line_items=[{
            'price': price_id_dict[price_type],
            'quantity': quantity,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'customer_id': customer_id,
            'price_type': price_type,
            'quantity': quantity
        }
    )

    return session

#todo HANDLE COMPLETION OF CHECKOUT SESSIONS (use webhooks) AND UPDATE STUDENT INFO IN DATABASE AND GOOGLE SHEET; after connected to domain and online