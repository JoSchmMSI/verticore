"""
Verticore — Pre-computed AI Cache
===================================
Stores validated verticals + build-priority features for the most common
SMB web-services verticals. Used as:
  1. Instant response for cached verticals (no API call needed)
  2. Fallback when Gemini free tier is rate-limited or unavailable

Each entry is exactly what the live AI would return:
  - validate_vertical() output schema
  - generate_build_priority() output schema (5 features, scored)

Covers 24 verticals across: beauty/personal care, food & hospitality,
home services, health & fitness, retail, professional services, repairs,
education, events, pets — the most common SMB web-services buyer segments.

To extend: add entries to VERTICAL_CACHE and FEATURE_CACHE.
Keys are lowercase, stripped, for fuzzy matching.
"""

# ── Validation cache ─────────────────────────────────────────────────────────
# Maps canonical search terms → validate_vertical() response dict
VALIDATION_CACHE = {
    # Beauty & Personal Care
    "beauty salon": {
        "valid": True, "canonical_name": "Beauty Salons & Hairdressers",
        "nace_code": "S9602", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 150, "reason": "High-volume SMB vertical, core web-services buyer"
    },
    "hair salon": {
        "valid": True, "canonical_name": "Hair Salons & Hairdressers",
        "nace_code": "S9602", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 150, "reason": "Major SMB vertical across all EU markets"
    },
    "hairdresser": {
        "valid": True, "canonical_name": "Hairdressers & Beauty Treatment",
        "nace_code": "S9602", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 150, "reason": "NACE 96.02 — large, digitising SMB segment"
    },
    "barber shop": {
        "valid": True, "canonical_name": "Barber Shops",
        "nace_code": "S9602", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 120, "reason": "High-frequency, appointment-driven SMB"
    },
    "nail salon": {
        "valid": True, "canonical_name": "Nail Salons",
        "nace_code": "S9602", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 130, "reason": "Fast-growing personal care sub-vertical"
    },
    "tattoo": {
        "valid": True, "canonical_name": "Tattoo & Piercing Studios",
        "nace_code": "S9609", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 140, "reason": "Appointment-based, strong online booking need"
    },
    "spa": {
        "valid": True, "canonical_name": "Spas & Wellness Centres",
        "nace_code": "S9602", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 200, "reason": "Higher ARPU wellness vertical, strong web presence need"
    },
    # Food & Hospitality
    "restaurant": {
        "valid": True, "canonical_name": "Restaurants & Food Service",
        "nace_code": "I5610", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 180, "reason": "Massive SMB segment, high online ordering & booking need"
    },
    "cafe": {
        "valid": True, "canonical_name": "Cafes & Coffee Shops",
        "nace_code": "I5630", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 120, "reason": "High footfall, loyalty and ordering use cases"
    },
    "bakeries": {
        "valid": True, "canonical_name": "Artisan Bakeries",
        "nace_code": "C1071", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 100, "reason": "Pre-order and e-commerce a key growth lever"
    },
    "bakery": {
        "valid": True, "canonical_name": "Artisan Bakeries",
        "nace_code": "C1071", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 100, "reason": "Pre-order and e-commerce a key growth lever"
    },
    "catering": {
        "valid": True, "canonical_name": "Catering Services",
        "nace_code": "I5621", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 200, "reason": "Quote/booking management a core digital need"
    },
    # Home Services & Trades
    "renovation": {
        "valid": True, "canonical_name": "Home Renovation & Building Trades",
        "nace_code": "F43", "adoption_group": "F",
        "arpu_eur": 200, "reason": "NACE F43 — large EU SMB segment, strong web lead-gen need"
    },
    "plumber": {
        "valid": True, "canonical_name": "Plumbing & Heating Services",
        "nace_code": "F4322", "adoption_group": "F",
        "arpu_eur": 180, "reason": "High-value trade, quote and booking key needs"
    },
    "electrician": {
        "valid": True, "canonical_name": "Electrical Installation Services",
        "nace_code": "F4321", "adoption_group": "F",
        "arpu_eur": 180, "reason": "Regulated trade, certification display and booking"
    },
    "landscaping": {
        "valid": True, "canonical_name": "Landscaping & Garden Services",
        "nace_code": "N8130", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 150, "reason": "Seasonal booking and portfolio display driven"
    },
    "cleaning": {
        "valid": True, "canonical_name": "Cleaning Services",
        "nace_code": "N8121", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 130, "reason": "High repeat-booking, review-driven acquisition"
    },
    # Auto Repair
    "auto repair": {
        "valid": True, "canonical_name": "Auto Repair & Maintenance",
        "nace_code": "G4520", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 180, "reason": "NACE G45.2 — large, digitising SMB segment"
    },
    "car repair": {
        "valid": True, "canonical_name": "Car Repair & Servicing",
        "nace_code": "G4520", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 180, "reason": "Booking, reminders and reviews are core digital needs"
    },
    # Health & Fitness
    "fitness": {
        "valid": True, "canonical_name": "Fitness Studios & Gyms",
        "nace_code": "R9313", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 100, "reason": "NACE R93.13 — membership and class booking driven"
    },
    "yoga": {
        "valid": True, "canonical_name": "Yoga & Pilates Studios",
        "nace_code": "R9313", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 110, "reason": "Class scheduling and membership management key"
    },
    "personal trainer": {
        "valid": True, "canonical_name": "Personal Training & Fitness Coaching",
        "nace_code": "R9313", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 130, "reason": "Online booking and client management core needs"
    },
    "physiotherapy": {
        "valid": True, "canonical_name": "Physiotherapy & Sports Therapy",
        "nace_code": "Q8690", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 160, "reason": "Appointment-driven, insurance and referral needs"
    },
    "dentist": {
        "valid": True, "canonical_name": "Dental Practices",
        "nace_code": "Q8621", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 200, "reason": "High-trust, appointment and recall management critical"
    },
    "vet": {
        "valid": True, "canonical_name": "Veterinary Clinics",
        "nace_code": "M7500", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 170, "reason": "Appointment, health records and pet owner portal"
    },
    "vet clinic": {
        "valid": True, "canonical_name": "Veterinary Clinics",
        "nace_code": "M7500", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 170, "reason": "Appointment, health records and pet owner portal"
    },
    "veterinary": {
        "valid": True, "canonical_name": "Veterinary Clinics",
        "nace_code": "M7500", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 170, "reason": "Appointment, health records and pet owner portal"
    },
    "optician": {
        "valid": True, "canonical_name": "Opticians & Eye Care",
        "nace_code": "Q8621", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 150, "reason": "Appointment and prescription management digital needs"
    },
    # Pets
    "dog grooming": {
        "valid": True, "canonical_name": "Dog Grooming & Pet Care",
        "nace_code": "S9609", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 110, "reason": "Appointment-driven, fast-growing owner-services vertical"
    },
    "pet shop": {
        "valid": True, "canonical_name": "Pet Shops & Supplies",
        "nace_code": "G4776", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 120, "reason": "E-commerce and subscription a key growth lever"
    },
    # Education & Coaching
    "tutoring": {
        "valid": True, "canonical_name": "Private Tutoring & Education",
        "nace_code": "P8559", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 120, "reason": "Online scheduling and payment management core needs"
    },
    "driving school": {
        "valid": True, "canonical_name": "Driving Schools",
        "nace_code": "P8553", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 130, "reason": "Lesson booking and theory test prep are key digital needs"
    },
    # Retail
    "florist": {
        "valid": True, "canonical_name": "Florists & Flower Shops",
        "nace_code": "G4776", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 110, "reason": "Online ordering and occasion-based marketing key"
    },
    "pharmacy": {
        "valid": True, "canonical_name": "Independent Pharmacies",
        "nace_code": "G4773", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 150, "reason": "Click-and-collect and prescription management growing"
    },
    # Events & Photography
    "photographer": {
        "valid": True, "canonical_name": "Photography Studios & Services",
        "nace_code": "M7420", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 160, "reason": "Portfolio, booking and client gallery are core needs"
    },
    "event planning": {
        "valid": True, "canonical_name": "Event Planning & Management",
        "nace_code": "N8230", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 200, "reason": "Quote, contract and guest management key digital needs"
    },
    # Sports clubs
    "sports club": {
        "valid": True, "canonical_name": "Sports Clubs & Associations",
        "nace_code": "R9312", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 100, "reason": "Membership and fixture management core needs"
    },
    "dance studio": {
        "valid": True, "canonical_name": "Dance Studios",
        "nace_code": "R9002", "adoption_group": "C10-S951_X_K",
        "arpu_eur": 110, "reason": "Class scheduling and student management driven"
    },
}

# ── Build-priority feature cache ─────────────────────────────────────────────
# Maps canonical_name → generate_build_priority() response (5 features)
# Scored with: priority = (pain_freq × wtp) / self_solve
FEATURE_CACHE = {
    "Beauty Salons & Hairdressers": [
        {"rank":1,"feature":"Online Booking & Scheduling","pain_point":"Clients call during appointments, causing missed bookings and double-bookings","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Highest-frequency pain, clients expect 24/7 booking, direct revenue impact","priority_score":4.5},
        {"rank":2,"feature":"Client Retention & Loyalty Program","pain_point":"No system to track client history or prompt rebooking at the right interval","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Reduces churn directly — repeat clients are 5× more profitable than new ones","priority_score":4.5},
        {"rank":3,"feature":"Instagram-to-Booking Link","pain_point":"Clients see work on Instagram but can't book without calling or DM-ing","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Closes the social-to-conversion gap where most discovery already happens","priority_score":3.0},
        {"rank":4,"feature":"Service Menu & Pricing Page","pain_point":"No clear price list online forces clients to call for basic info","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Reduces admin calls, sets expectations, improves conversion from search","priority_score":2.0},
        {"rank":5,"feature":"Review Collection & Display","pain_point":"Happy clients rarely leave reviews without a prompt, hurting local SEO","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Reviews are the #1 local discovery driver — automated collection multiplies output","priority_score":3.0},
    ],
    "Yoga & Pilates Studios": [
        {"rank":1,"feature":"Class Schedule & Online Booking","pain_point":"Students can't see class availability or book without calling or emailing","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Class-based businesses live and die by scheduling — it is the core product","priority_score":4.5},
        {"rank":2,"feature":"Membership & Pass Management","pain_point":"Tracking class passes and memberships manually causes errors and revenue leakage","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Recurring revenue from memberships needs automated management to scale","priority_score":4.5},
        {"rank":3,"feature":"Waitlist & Cancellation Fill","pain_point":"Cancelled spots go unfilled because there is no automated waitlist system","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Every unfilled spot is pure lost revenue — automation recovers it with zero effort","priority_score":3.0},
        {"rank":4,"feature":"New Student Onboarding Flow","pain_point":"First-timers arrive unprepared, slowing down class start and frustrating regulars","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Digital intake and waivers reduce admin and create a professional first impression","priority_score":2.0},
        {"rank":5,"feature":"Instructor Bio & Class Description Pages","pain_point":"Prospective students can't decide which class or instructor suits them","self_solve_ability":"medium","willingness_to_pay":"low","pain_frequency":"medium","why_it_wins":"Reduces no-shows from mismatched expectations, improves conversion","priority_score":1.0},
    ],
    "Restaurants & Food Service": [
        {"rank":1,"feature":"Online Table Reservation","pain_point":"Phone reservations are missed outside opening hours, losing walk-in business","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"24/7 booking captures demand that currently goes to competitors on OpenTable","priority_score":4.5},
        {"rank":2,"feature":"Digital Menu with QR Code","pain_point":"Printed menus are expensive to update and create hygiene concerns","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Low cost, high-frequency use, enables daily specials and pricing flexibility","priority_score":3.0},
        {"rank":3,"feature":"Click & Collect / Takeaway Ordering","pain_point":"Phone takeaway orders are error-prone and tie up staff during peak hours","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Direct ordering avoids 20–30% third-party delivery commissions","priority_score":4.5},
        {"rank":4,"feature":"Loyalty & Repeat Visit Program","pain_point":"No mechanism to incentivise return visits beyond informal punch cards","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Restaurant loyalty is proven to increase visit frequency by 20–30%","priority_score":3.0},
        {"rank":5,"feature":"Private Event & Group Booking Page","pain_point":"Enquiries for private dining or large groups require back-and-forth by phone","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"High-value bookings currently lost due to friction in the enquiry process","priority_score":2.0},
    ],
    "Home Renovation & Building Trades": [
        {"rank":1,"feature":"Quote Request & Lead Capture Form","pain_point":"Potential clients can't request a quote outside business hours, going to a competitor","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Lead capture is the primary revenue driver for trades — every missed lead is lost revenue","priority_score":4.5},
        {"rank":2,"feature":"Project Portfolio Gallery","pain_point":"Tradespeople can't show before/after work to prospects without meeting them first","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Visual proof of quality is the single most powerful trust signal in trades","priority_score":3.0},
        {"rank":3,"feature":"Verified Review Display","pain_point":"Reviews scattered across Google and Facebook can't be controlled or showcased","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Trades are referral-driven — curated reviews on their own site multiply trust","priority_score":3.0},
        {"rank":4,"feature":"Certification & Accreditation Badges","pain_point":"Customers can't verify trade qualifications online, creating trust barriers","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Displaying gas-safe, NICEIC, or similar badges directly increases conversion","priority_score":3.0},
        {"rank":5,"feature":"Job Tracking Client Portal","pain_point":"Clients repeatedly call for progress updates on ongoing renovation work","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"A simple progress update portal reduces inbound calls by 40–60%","priority_score":3.0},
    ],
    "Auto Repair & Maintenance": [
        {"rank":1,"feature":"Online Service Booking","pain_point":"Customers can't book a service slot without calling during business hours","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Reduces phone load and fills workshop capacity without staff involvement","priority_score":4.5},
        {"rank":2,"feature":"Service Reminder & MOT Alert","pain_point":"Customers forget service intervals, reducing return visits and creating liability risk","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Automated reminders are the single biggest driver of repeat business in auto repair","priority_score":4.5},
        {"rank":3,"feature":"Digital Vehicle Health Report","pain_point":"Paper inspection sheets are lost and customers don't trust verbal-only recommendations","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Digital reports with photos increase upsell acceptance rate significantly","priority_score":3.0},
        {"rank":4,"feature":"Transparent Pricing & Service Menu","pain_point":"Customers distrust garages partly because pricing is opaque until the job is done","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Price transparency is the #1 trust differentiator in a low-trust category","priority_score":3.0},
        {"rank":5,"feature":"Customer Review & Rating Display","pain_point":"Honest garages can't distinguish themselves from disreputable ones in search results","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Reviews on the garage's own site build trust that Google reviews alone can't","priority_score":3.0},
    ],
    "Fitness Studios & Gyms": [
        {"rank":1,"feature":"Membership Sign-Up & Management","pain_point":"New members join via paper forms and payments are tracked in spreadsheets","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Membership is the core revenue model — digital management directly drives retention","priority_score":4.5},
        {"rank":2,"feature":"Class Timetable & Booking","pain_point":"Members can't see live class availability or book without calling or emailing","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Real-time class booking is the baseline expectation — absence causes churn","priority_score":4.5},
        {"rank":3,"feature":"Member App / Mobile-First Portal","pain_point":"Members check timetables on desktop only — mobile experience is broken","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"70%+ of fitness searches happen on mobile — a poor mobile experience loses members","priority_score":3.0},
        {"rank":4,"feature":"PT Booking & Personal Training Upsell","pain_point":"Personal training sessions are sold informally, with no system for recurring bookings","self_solve_ability":"medium","willingness_to_pay":"high","pain_frequency":"medium","why_it_wins":"PT is 3–5× higher revenue than membership — a booking system directly grows ARPU","priority_score":3.0},
        {"rank":5,"feature":"Trial Pass & Intro Offer Landing Page","pain_point":"No dedicated conversion page for first-timers means high drop-off from ads","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Trial offers are the highest-converting acquisition tool in fitness","priority_score":2.0},
    ],
    "Artisan Bakeries": [
        {"rank":1,"feature":"Pre-Order & Click-and-Collect","pain_point":"Popular items sell out before some customers arrive, causing frustration and lost sales","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Pre-orders guarantee revenue, reduce waste and smooth production planning","priority_score":4.5},
        {"rank":2,"feature":"Custom Cake & Order Request Form","pain_point":"Custom orders are taken by phone/DM, with no system to manage specifications or deposits","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Custom orders are highest-margin — a structured form reduces errors and no-shows","priority_score":4.5},
        {"rank":3,"feature":"Weekly Bake Schedule & Product Listing","pain_point":"Regulars don't know what's available on which day and call to ask","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Publishing weekly availability drives footfall planning and reduces inbound calls","priority_score":3.0},
        {"rank":4,"feature":"Subscription Box / Regular Order","pain_point":"Loyal customers want a recurring weekly order but there's no mechanism for it","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"medium","why_it_wins":"Subscription revenue is the most predictable and loyal income stream for bakeries","priority_score":3.0},
        {"rank":5,"feature":"Corporate & Event Catering Enquiry Page","pain_point":"Office and event orders are fielded ad-hoc with no clear process","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"B2B catering is 3–10× a retail sale with higher predictability","priority_score":2.0},
    ],
    "Dog Grooming & Pet Care": [
        {"rank":1,"feature":"Online Appointment Booking","pain_point":"Owners can't book outside of business hours — groomers miss calls while working","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Grooming is entirely appointment-based — online booking is the product","priority_score":4.5},
        {"rank":2,"feature":"Pet Profile & Grooming History","pain_point":"Groomers don't have notes on returning pets' preferences, allergies or last visit","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Pet profiles build loyalty and reduce errors — owners feel valued and understood","priority_score":3.0},
        {"rank":3,"feature":"Before & After Gallery","pain_point":"Prospective clients can't see the groomer's work quality before booking","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Visual proof of results is the primary trust signal in a high-care-concern vertical","priority_score":3.0},
        {"rank":4,"feature":"Automated Rebooking Reminders","pain_point":"Owners forget to rebook 6–8 weeks after a groom, creating irregular revenue","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Timely reminders are proven to increase rebooking rates by 30–50%","priority_score":3.0},
        {"rank":5,"feature":"Service Menu & Breed-Specific Pricing","pain_point":"Owners don't know costs upfront and call to ask, wasting staff time","self_solve_ability":"medium","willingness_to_pay":"low","pain_frequency":"medium","why_it_wins":"Transparent pricing reduces friction and pre-qualifies buyers before contact","priority_score":1.0},
    ],
    "Photography Studios & Services": [
        {"rank":1,"feature":"Portfolio Gallery & Style Showcase","pain_point":"Prospective clients can't assess style fit before making contact","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Portfolio quality is the sole buying criterion — its online presentation is everything","priority_score":3.0},
        {"rank":2,"feature":"Booking & Session Enquiry Form","pain_point":"Enquiries come via DM and email in no structured format, losing information","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Structured enquiry with date/type/budget pre-qualifies leads and saves hours","priority_score":4.5},
        {"rank":3,"feature":"Client Proofing & Image Delivery Gallery","pain_point":"Sharing final images via Google Drive or WeTransfer looks unprofessional","self_solve_ability":"medium","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"A branded delivery gallery is a premium touchpoint that generates referrals","priority_score":3.0},
        {"rank":4,"feature":"Package Pricing Page","pain_point":"No clear package pricing forces every prospect into a consultation call","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Transparent pricing filters serious buyers and reduces time-wasting enquiries","priority_score":2.0},
        {"rank":5,"feature":"Review & Testimonial Display","pain_point":"Happy clients rarely leave Google reviews without prompting","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Social proof is the second-most important factor after portfolio in photographer selection","priority_score":3.0},
    ],
    "Cleaning Services": [
        {"rank":1,"feature":"Instant Online Quote & Booking","pain_point":"Getting a cleaning quote requires a callback, during which the prospect books a competitor","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Speed to quote wins in cleaning — instant online quoting converts before a call can","priority_score":4.5},
        {"rank":2,"feature":"Recurring Booking Subscription","pain_point":"Regular clients have to re-book manually each time instead of a standing order","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Recurring contracts are the only route to predictable revenue in cleaning","priority_score":4.5},
        {"rank":3,"feature":"Verified Review Display","pain_point":"Trust is the primary barrier in home-access services — reviews are the solution","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Reviews directly address the home-access trust barrier that prevents first bookings","priority_score":3.0},
        {"rank":4,"feature":"Service Area & Coverage Map","pain_point":"Prospective clients don't know if the cleaner operates in their postcode","self_solve_ability":"medium","willingness_to_pay":"low","pain_frequency":"medium","why_it_wins":"A coverage map eliminates the most common wasted enquiry type","priority_score":1.0},
        {"rank":5,"feature":"Before & After Gallery","pain_point":"Clients can't assess cleaning quality until after the first visit","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Visual evidence of results builds pre-purchase confidence in a high-trust-barrier category","priority_score":2.0},
    ],
    "Veterinary Clinics": [
        {"rank":1,"feature":"Online Appointment Booking","pain_point":"Pet owners can't book routine appointments without calling during clinic hours","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Vets are appointment-driven businesses — 24/7 booking directly increases capacity utilisation","priority_score":4.5},
        {"rank":2,"feature":"Pet Health Record & Vaccination Reminder","pain_point":"Owners forget vaccination and treatment schedules, creating health risks and missed revenue","self_solve_ability":"low","willingness_to_pay":"high","pain_frequency":"high","why_it_wins":"Automated reminders are the single best retention tool in veterinary practice","priority_score":4.5},
        {"rank":3,"feature":"Online Prescription & Product Ordering","pain_point":"Repeat prescriptions and flea/worm treatments require a visit or a call","self_solve_ability":"low","willingness_to_pay":"medium","pain_frequency":"high","why_it_wins":"Click-to-reorder for repeat products is a high-margin, frictionless revenue stream","priority_score":3.0},
        {"rank":4,"feature":"New Patient Registration Form","pain_point":"First-visit paperwork is filled in by hand in the waiting room, slowing intake","self_solve_ability":"medium","willingness_to_pay":"medium","pain_frequency":"medium","why_it_wins":"Digital intake reduces appointment time and creates a professional first impression","priority_score":2.0},
        {"rank":5,"feature":"Emergency Out-of-Hours Guidance","pain_point":"Owners panic-search when something goes wrong and don't know where to go","self_solve_ability":"medium","willingness_to_pay":"low","pain_frequency":"medium","why_it_wins":"An out-of-hours guidance page builds trust and becomes the #1 local SEO landing page","priority_score":1.0},
    ],
}

# ── Fuzzy matching helpers ────────────────────────────────────────────────────
def _normalise(text):
    """Lowercase, strip, remove common filler words for matching."""
    text = text.lower().strip()
    for filler in ["shop", "studio", "services", "service", "the ", "a ", "an "]:
        text = text.replace(filler, " ")
    return " ".join(text.split())

def get_cached_validation(raw_input):
    """
    Try to find a cached validation result for the raw input.
    Returns the cached dict or None if no match found.
    Matches on: exact key, partial key overlap, or canonical name match.
    """
    normalised = _normalise(raw_input)
    
    # 1. Direct key match
    if normalised in VALIDATION_CACHE:
        return VALIDATION_CACHE[normalised]
    
    # 2. Partial match — input contains a cache key or vice versa
    for key, val in VALIDATION_CACHE.items():
        if key in normalised or normalised in key:
            return val
    
    # 3. Word overlap — any cache key word appears in input
    input_words = set(normalised.split())
    best_match = None
    best_overlap = 0
    for key, val in VALIDATION_CACHE.items():
        key_words = set(key.split())
        overlap = len(input_words & key_words)
        if overlap > best_overlap and overlap >= 1:
            best_overlap = overlap
            best_match = val
    if best_match and best_overlap >= 1:
        return best_match
    
    return None

def get_cached_features(canonical_name):
    """
    Try to find cached build-priority features for the canonical vertical name.
    Returns list of features or None.
    """
    # Direct match
    if canonical_name in FEATURE_CACHE:
        return FEATURE_CACHE[canonical_name]
    
    # Partial canonical name match
    normalised = canonical_name.lower()
    for key, val in FEATURE_CACHE.items():
        if key.lower() in normalised or normalised in key.lower():
            return val
    
    # Word overlap on canonical name
    input_words = set(normalised.split())
    for key, val in FEATURE_CACHE.items():
        key_words = set(key.lower().split())
        if len(input_words & key_words) >= 1:
            return val
    
    return None

def list_cached_verticals():
    """Return all cached vertical canonical names for UI hints."""
    return sorted(set(v["canonical_name"] for v in VALIDATION_CACHE.values()))
