"""
Development-only demo data: teams, categories, users for all roles, knowledge-base
articles and ~45 tickets spread over the last 6 weeks.

    python manage.py seed_demo            # create (skips if demo data already exists)
    python manage.py seed_demo --reset    # delete demo tickets/articles and recreate

No AI output is fabricated: tickets are created without AI insights. Use "Run AI analysis"
in the UI (with a GEMINI_API_KEY configured) to generate real ones.
"""

import os
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Team, User
from apps.knowledge_base.models import KnowledgeBaseArticle
from apps.tickets.models import (
    Category,
    SLAPolicy,
    Ticket,
    TicketActivity,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import compute_sla_due

DEMO_DOMAIN = "opsdesk.dev"

TEAMS = {"Technical Support": "Product issues, bugs and access problems", "Billing": "Payments, invoices and plans"}

CATEGORIES = [
    ("Technical Issue", "Bugs, errors and things not working", "Technical Support"),
    ("Account Access", "Login, password and two-factor problems", "Technical Support"),
    ("Billing", "Payments, invoices, refunds and plan changes", "Billing"),
    ("Feature Request", "Ideas and suggestions", None),
    ("General Inquiry", "Questions that don't fit elsewhere", None),
]

USERS = [
    ("admin", "Ananya", "Iyer", User.Role.ADMIN, None),
    ("priya.agent", "Priya", "Sharma", User.Role.AGENT, "Technical Support"),
    ("neha.agent", "Neha", "Verma", User.Role.AGENT, "Technical Support"),
    ("rahul.agent", "Rahul", "Nair", User.Role.AGENT, "Billing"),
    ("customer", "Aarav", "Mehta", User.Role.CUSTOMER, None),
    ("sara.customer", "Sara", "Thomas", User.Role.CUSTOMER, None),
    ("john.customer", "John", "Dsouza", User.Role.CUSTOMER, None),
]

ARTICLES = [
    ("How to reset your password", "Account Access", "public",
     "If you forgot your password, open the login page and click **Forgot password**. Enter the email address of "
     "your account and we will send a reset link that is valid for 30 minutes. The link can be used once. If the "
     "email does not arrive within 5 minutes, check your spam folder and make sure you used the email address you "
     "signed up with. For security reasons, support agents cannot see or set your password for you. After five "
     "failed login attempts your account is locked for 15 minutes; waiting or resetting your password unlocks it."),
    ("Setting up two-factor authentication (2FA)", "Account Access", "public",
     "Two-factor authentication adds a one-time code to your login. Go to Settings > Security > Two-factor "
     "authentication, click Enable, and scan the QR code with an authenticator app such as Google Authenticator or "
     "Authy. Enter the 6-digit code to confirm. Save your 10 backup codes in a safe place. If you lose access to "
     "your authenticator app, use a backup code to log in and then disable and re-enable 2FA. If you have no "
     "backup codes, contact support from your account email; identity verification takes 1-2 business days."),
    ("Downloading invoices and receipts", "Billing", "public",
     "Invoices are generated on the first day of each billing cycle. To download one, go to Settings > Billing > "
     "Invoices and click the PDF icon next to the invoice. Only account owners and billing admins can see "
     "invoices. To add your company name, address or GST/VAT number to future invoices, edit Billing details "
     "before the next billing date; past invoices cannot be changed."),
    ("Refund and cancellation policy", "Billing", "public",
     "You can cancel your subscription at any time from Settings > Billing > Plan. Cancellation takes effect at "
     "the end of the current billing period and you keep access until then. Monthly plans are not refunded for "
     "partial months. Annual plans can be refunded in full within 14 days of purchase or renewal. Duplicate "
     "charges are always refunded; refunds take 5-7 business days to appear on your statement."),
    ("Updating your payment method", "Billing", "public",
     "To change the card used for your subscription, go to Settings > Billing > Payment method and click Update. "
     "We accept Visa, Mastercard, American Express and RuPay cards, and UPI AutoPay for customers in India. "
     "If a payment fails, we retry three times over 7 days and email the account owner each time. Your account "
     "stays active during the retry period."),
    ("API rate limits", "Technical Issue", "public",
     "The REST API allows 100 requests per minute per API key on the Starter plan and 1,000 per minute on the "
     "Business plan. When you exceed the limit the API returns HTTP 429 with a Retry-After header. Use "
     "exponential backoff and cache responses where possible. Rate limits are applied per key, so creating more "
     "keys for the same integration does not increase the limit."),
    ("Troubleshooting slow dashboard loading", "Technical Issue", "public",
     "If dashboards load slowly, first check status.example.com for ongoing incidents. Then try a hard refresh "
     "(Ctrl+Shift+R), disable browser extensions, and test in a private window. Dashboards with more than 20 "
     "widgets or date ranges longer than 12 months can take up to 30 seconds; narrowing the date range helps. "
     "If the problem continues, send us your browser version and a screenshot of the Network tab."),
    ("Exporting your data", "General Inquiry", "public",
     "Account owners can export all data from Settings > Data > Export. Choose CSV or JSON and the date range. "
     "Exports are prepared in the background and a download link is emailed within 30 minutes. Links expire after "
     "7 days. Exports larger than 2 GB are split into multiple files."),
    ("Escalation playbook for urgent incidents", "Technical Issue", "internal",
     "Internal: for URGENT tickets that report an outage or data loss, acknowledge the customer within 15 minutes, "
     "assign the ticket to yourself, and post in the #incidents channel with the ticket number. Do not promise a "
     "fix time. Update the customer at least every 2 hours until resolved. After resolution, add an internal note "
     "with the root cause and link the incident report."),
    ("Handling chargebacks and disputed payments", "Billing", "internal",
     "Internal: never discuss chargeback outcomes or promise refunds in writing before the billing lead approves. "
     "Collect the transaction ID and date, tag the ticket as Billing / High priority, and assign it to the "
     "Billing team. Chargebacks must be answered within 5 days of notification."),
]
DRAFT_ARTICLE = ("Single sign-on (SSO) setup - draft", "Account Access", "public",
                 "Draft article: SAML SSO setup steps for Business plan customers. To be completed by the identity team.")

TICKET_TEMPLATES = [
    ("Cannot log in after password reset", "I reset my password this morning but the login page still says my "
     "credentials are invalid. I have tried three times and now it says my account is locked.", "Account Access"),
    ("Charged twice for this month's subscription", "My bank statement shows two charges of Rs 2,499 on the same "
     "day for the Business plan. Please refund the duplicate payment.", "Billing"),
    ("Dashboard takes over a minute to load", "Since yesterday our main dashboard takes 60+ seconds to load and "
     "sometimes times out. Other pages are fine.", "Technical Issue"),
    ("API returning 429 errors", "Our integration started getting HTTP 429 responses even though we only make about "
     "50 requests per minute. This is blocking our nightly sync.", "Technical Issue"),
    ("Need GST number on invoices", "Please add our company GST number to the invoices. We need corrected invoices "
     "for the last quarter for our accounts team.", "Billing"),
    ("Lost my phone with the authenticator app", "I lost my phone and can't get the 2FA code. I don't have the "
     "backup codes. How can I get back into my account?", "Account Access"),
    ("Production outage - all users see error 500", "None of our 200 users can access the app. Every page shows "
     "error 500. This started 20 minutes ago and our whole team is blocked.", "Technical Issue"),
    ("Request: dark mode", "It would be great to have a dark mode option. Many of our team members work late.",
     "Feature Request"),
    ("How do I export all my data?", "We are doing an internal audit and need a full export of our account data. "
     "What formats are available?", "General Inquiry"),
    ("Card payment keeps failing", "We updated our card but the payment still fails. We got an email saying the "
     "account will be suspended. Please help.", "Billing"),
    ("Cancel annual plan and refund", "We bought the annual plan 10 days ago but it doesn't fit our needs. We would "
     "like to cancel and get a refund.", "Billing"),
    ("Webhook deliveries are delayed", "Webhook events are arriving 10-15 minutes late since the last update. Is "
     "there an incident?", "Technical Issue"),
    ("Add more seats to our plan", "We need to add 5 more users to our workspace. Will we be charged pro-rata?",
     "Billing"),
    ("CSV export has broken characters", "When I export to CSV, names with accents or Hindi characters show up as "
     "random symbols in Excel.", "Technical Issue"),
    ("Integration with Slack", "Do you have a Slack integration for notifications? If not, is it on the roadmap?",
     "Feature Request"),
]

AGENT_REPLIES = [
    "Thanks for reaching out. I'm looking into this now and will update you shortly.",
    "Thank you for the details. Could you share a screenshot of the error and the time it happened?",
    "I've checked your account and found the cause. I've applied a fix on our side - could you try again?",
    "Thanks for your patience. This has been resolved. Please let us know if you see the problem again.",
]
CUSTOMER_FOLLOWUPS = [
    "Thanks, here is the screenshot you asked for. It happened around 10:30 AM.",
    "I tried again and it works now. Thank you!",
    "It's still happening for some of our users.",
]
INTERNAL_NOTES = [
    "Checked the logs - looks related to the cache change deployed on Monday.",
    "Customer is on the Business plan, prioritise.",
    "Waiting for the billing team to confirm the duplicate charge.",
]


class Command(BaseCommand):
    help = "Create demo users, categories, knowledge-base articles and tickets (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing tickets and articles first.")
        parser.add_argument("--allow-production", action="store_true",
                            help="Allow running with DJANGO_DEBUG=False (never on a real production database).")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("seed_demo only runs with DJANGO_DEBUG=True (or pass --allow-production).")
        password = os.environ.get("DEMO_PASSWORD", "OpsDesk@2026")
        rng = random.Random(42)

        with transaction.atomic():
            if options["reset"]:
                Ticket.objects.all().delete()
                KnowledgeBaseArticle.objects.all().delete()
            elif Ticket.objects.exists():
                self.stdout.write(self.style.WARNING("Tickets already exist - nothing to do (use --reset)."))
                return

            for priority, hours in settings.DEFAULT_SLA_HOURS.items():
                SLAPolicy.objects.get_or_create(priority=priority, defaults={"resolution_hours": hours})
            teams = {name: Team.objects.get_or_create(name=name, defaults={"description": d})[0]
                     for name, d in TEAMS.items()}
            categories = {}
            for name, desc, team in CATEGORIES:
                categories[name], _ = Category.objects.update_or_create(
                    name=name, defaults={"description": desc, "team": teams.get(team), "is_active": True}
                )
            users = {}
            for local, first, last, role, team in USERS:
                email = f"{local}@{DEMO_DOMAIN}"
                user, created = User.objects.get_or_create(
                    email=email, defaults={"first_name": first, "last_name": last, "role": role, "team": teams.get(team)}
                )
                if created:
                    user.set_password(password)
                    if role == User.Role.ADMIN:
                        user.is_staff = user.is_superuser = True  # can also use /admin/
                    user.save()
                users[local] = user

            admin = users["admin"]
            for title, cat, visibility, content in ARTICLES:
                KnowledgeBaseArticle.objects.create(
                    title=title, slug=slugify(title), summary=content[:160].rsplit(" ", 1)[0] + "...",
                    content=content, category=categories[cat], status="published", visibility=visibility,
                    author=admin, published_at=timezone.now() - timedelta(days=60),
                )
            title, cat, visibility, content = DRAFT_ARTICLE
            KnowledgeBaseArticle.objects.create(title=title, slug=slugify(title), content=content,
                                                category=categories[cat], status="draft", visibility=visibility,
                                                author=admin)

            self._create_tickets(rng, users, categories)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Log in with any of these accounts (password: {password}):"
        ))
        for local, *_ in USERS:
            self.stdout.write(f"  {local}@{DEMO_DOMAIN}")

    def _create_tickets(self, rng, users, categories):
        now = timezone.now()
        customers = [users["customer"], users["sara.customer"], users["john.customer"]]
        agents_by_team = {
            "Technical Support": [users["priya.agent"], users["neha.agent"]],
            "Billing": [users["rahul.agent"]],
            None: [users["priya.agent"], users["neha.agent"], users["rahul.agent"]],
        }
        priority_for = {
            "Production outage - all users see error 500": TicketPriority.URGENT,
            "Charged twice for this month's subscription": TicketPriority.HIGH,
            "API returning 429 errors": TicketPriority.HIGH,
            "Lost my phone with the authenticator app": TicketPriority.HIGH,
            "Card payment keeps failing": TicketPriority.HIGH,
            "Request: dark mode": TicketPriority.LOW,
            "Integration with Slack": TicketPriority.LOW,
        }
        for i in range(45):
            title, description, cat_name = TICKET_TEMPLATES[i % len(TICKET_TEMPLATES)]
            category = categories[cat_name]
            priority = priority_for.get(title, rng.choice([TicketPriority.MEDIUM, TicketPriority.MEDIUM,
                                                            TicketPriority.LOW, TicketPriority.HIGH]))
            days_ago = rng.uniform(0.2, 6) if i % 5 in (0, 1, 2) else rng.uniform(6, 42)
            created_at = now - timedelta(days=days_ago, hours=rng.uniform(0, 4))
            age_hours = (now - created_at).total_seconds() / 3600
            # Older tickets are mostly resolved/closed; recent ones are mostly active.
            if age_hours > 24 * 10:
                status = rng.choice([TicketStatus.CLOSED, TicketStatus.CLOSED, TicketStatus.RESOLVED,
                                     TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS])
            else:
                status = rng.choice([TicketStatus.OPEN, TicketStatus.OPEN, TicketStatus.IN_PROGRESS,
                                     TicketStatus.WAITING_FOR_CUSTOMER, TicketStatus.RESOLVED])
            team_name = category.team.name if category.team else None
            agent = None if status == TicketStatus.OPEN and rng.random() < 0.6 else rng.choice(agents_by_team[team_name])

            ticket = Ticket.objects.create(
                title=title, description=description, customer=customers[i % 3], category=category,
                priority=priority, status=status, assigned_agent=agent, created_at=created_at,
                sla_due_at=compute_sla_due(created_at, priority),
            )
            ticket.number = f"OPS-{ticket.pk:06d}"
            TicketActivity.objects.create(ticket=ticket, actor=ticket.customer, action="created",
                                          to_value=TicketStatus.OPEN, is_public=True, created_at=created_at)

            t = created_at
            responder = agent or rng.choice(agents_by_team[team_name])
            if status != TicketStatus.OPEN or agent:
                t = min(t + timedelta(hours=rng.uniform(0.3, 6)), now - timedelta(minutes=40))
                TicketMessage.objects.create(ticket=ticket, author=responder, body=rng.choice(AGENT_REPLIES[:2]),
                                             created_at=t)
                ticket.first_response_at = t
                if rng.random() < 0.5:
                    TicketMessage.objects.create(ticket=ticket, author=responder, body=rng.choice(INTERNAL_NOTES),
                                                 is_internal=True, created_at=t + timedelta(minutes=10))
                if rng.random() < 0.6:
                    t = min(t + timedelta(hours=rng.uniform(1, 12)), now - timedelta(minutes=20))
                    TicketMessage.objects.create(ticket=ticket, author=ticket.customer,
                                                 body=rng.choice(CUSTOMER_FOLLOWUPS), created_at=t)
            if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                sla_hours = (ticket.sla_due_at - created_at).total_seconds() / 3600
                # ~80% within SLA, ~20% breached, never in the future.
                factor = rng.uniform(0.2, 0.95) if rng.random() < 0.8 else rng.uniform(1.1, 1.8)
                resolved_at = min(created_at + timedelta(hours=sla_hours * factor), now - timedelta(minutes=5))
                resolved_at = max(resolved_at, t + timedelta(minutes=5))
                resolved_at = min(resolved_at, now - timedelta(minutes=1))
                TicketMessage.objects.create(ticket=ticket, author=responder, body=AGENT_REPLIES[3],
                                             created_at=resolved_at)
                ticket.resolved_at = resolved_at
                TicketActivity.objects.create(ticket=ticket, actor=responder, action="status_changed",
                                              from_value=TicketStatus.IN_PROGRESS, to_value=TicketStatus.RESOLVED,
                                              is_public=True, created_at=resolved_at)
                if status == TicketStatus.CLOSED:
                    ticket.closed_at = min(resolved_at + timedelta(days=1), now)
            ticket.save()
