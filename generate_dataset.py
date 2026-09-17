import random
import re
import pandas as pd
import numpy as np

SYSTEM_PROMPT = "You are a Fake Job Detection AI trained on Indian job postings from platforms like LinkedIn, Naukri, Internshala, Indeed, and direct applications."

random.seed(42)
np.random.seed(42)

# Indian Tier-1 & Tier-2 Tech & Industrial Hubs
CITIES = [
    "Bangalore", "Bengaluru", "Hyderabad", "Pune", "Noida", "Gurugram", "Gurgaon",
    "Mumbai", "Chennai", "Delhi NCR", "Kolkata", "Ahmedabad", "Kochi", "Indore",
    "Jaipur", "Chandigarh", "Coimbatore", "Bhubaneswar", "Nagpur", "Trivandrum",
    "Vadodara", "Lucknow", "Visakhapatnam", "Surat", "Mysore", "Bhopal"
]

# Genuine Tech Roles with rich variety
TECH_SPECS = [
    ("Frontend Developer", ["React.js", "Next.js", "TypeScript", "Tailwind CSS"], "3.5-7 LPA", "1-3 yrs"),
    ("Senior Frontend Engineer", ["React", "Redux Toolkit", "Webpack", "Performance Optimization", "Next.js"], "16-25 LPA", "4-7 yrs"),
    ("Backend Engineer (Python/FastAPI)", ["Python 3.11", "FastAPI", "PostgreSQL", "Celery", "Redis", "Docker"], "8-15 LPA", "2-5 yrs"),
    ("Backend Engineer (Go)", ["Golang", "gRPC", "Microservices", "Kafka", "Kubernetes"], "14-24 LPA", "3-6 yrs"),
    ("Java Spring Boot Developer", ["Java 17", "Spring Boot", "Hibernate", "Microservices", "MySQL", "AWS"], "7-13 LPA", "2-5 yrs"),
    ("Full Stack Engineer (MERN)", ["Node.js", "Express", "React", "MongoDB", "Tailwind CSS"], "5-10 LPA", "1-4 yrs"),
    ("Data Engineer", ["Apache Spark", "PySpark", "Snowflake", "dbt", "Airflow", "SQL"], "12-22 LPA", "3-6 yrs"),
    ("Machine Learning Engineer", ["PyTorch", "Hugging Face", "MLflow", "FastAPI", "Docker", "NLP"], "15-28 LPA", "2-5 yrs"),
    ("DevOps / SRE Engineer", ["Terraform", "Kubernetes", "AWS EKS", "CI/CD GitHub Actions", "Prometheus", "Grafana"], "12-22 LPA", "3-6 yrs"),
    ("QA Automation Engineer", ["Selenium", "Playwright", "Java", "TestNG", "RestAssured", "CI/CD"], "5-10 LPA", "2-4 yrs"),
    ("Mobile Developer (Flutter)", ["Flutter", "Dart", "BLoC / Provider", "REST APIs", "App Store deployment"], "6-12 LPA", "2-4 yrs"),
    ("Mobile Developer (React Native)", ["React Native", "TypeScript", "Redux", "Native Modules", "Firebase"], "7-14 LPA", "2-5 yrs"),
    ("Cybersecurity Analyst", ["SOC Tier 1/2", "SIEM", "Splunk", "Network Security", "VAPT", "Wireshark"], "8-15 LPA", "2-4 yrs"),
    ("Cloud Solutions Architect", ["AWS / Azure", "Microservices", "System Design", "Cost Optimization", "Security Architecture"], "25-40 LPA", "7-12 yrs"),
    ("Product Designer (UI/UX)", ["Figma", "Design Systems", "User Research", "Wireframing", "Interaction Design"], "9-18 LPA", "2-5 yrs"),
    ("Data Analyst", ["SQL", "PowerBI", "Tableau", "Python", "Data Modeling", "Excel"], "5-9 LPA", "1-3 yrs")
]

# Genuine Non-Tech Roles
NON_TECH_SPECS = [
    ("Business Development Executive (B2B)", "Outbound prospecting, CRM management, discovery calls, client pitches", "3.5-5.5 LPA + incentives", "0-2 yrs"),
    ("Senior Account Executive", "Enterprise sales cycle, solution pitching, contract negotiation, quota attainment", "10-18 LPA + OTE", "3-6 yrs"),
    ("HR Generalist & Talent Acquisition", "Full lifecycle recruitment, campus hiring, HRMS, onboarding, payroll compliance", "4-7.5 LPA", "1-4 yrs"),
    ("Content Strategist / Copywriter", "B2B SaaS copy, case studies, SEO articles, email newsletters", "4-7 LPA", "1-3 yrs"),
    ("Customer Success Manager", "Key account onboarding, retention, QBRs, upsell identification, customer health tracking", "7-14 LPA", "2-5 yrs"),
    ("Financial Analyst", "Budgeting, variance analysis, financial modeling, MIS dashboards, working capital", "6-11 LPA", "2-4 yrs"),
    ("Performance Marketing Specialist", "Google Ads, Meta Ads Manager, ROAS optimization, funnel analytics, Google Tag Manager", "6-12 LPA", "2-4 yrs"),
    ("Supply Chain Operations Executive", "Inventory forecasting, 3PL coordination, warehouse dispatch tracking, vendor management", "4-6.5 LPA", "1-3 yrs"),
    ("Graphic Designer & Brand Specialist", "Adobe Photoshop, Illustrator, motion graphics, branding guidelines, social creatives", "4-7 LPA", "1-4 yrs"),
    ("Corporate Legal Counsel", "Commercial agreement drafting, vendor MSAs, DPDP Act compliance, NDAs", "8-15 LPA", "2-5 yrs"),
    ("Technical Recruiter", "Sourcing software engineers, candidate screening, compensation negotiation, ATS management", "5-9 LPA", "2-4 yrs")
]

# Genuine Internships
INTERNSHIP_SPECS = [
    ("Software Development Intern", "Python / Node.js or React basics, Git workflow", "INR 15,000 - 25,000 /month", "3-6 months"),
    ("Data Science & Analytics Intern", "Python, pandas, SQL, exploratory data analysis", "INR 18,000 - 28,000 /month", "6 months"),
    ("Digital Marketing Intern", "SEO research, Canva, social media scheduling, campaign tracking", "INR 8,000 - 15,000 /month", "3 months"),
    ("HR & Recruitment Intern", "Screening resumes on Naukri/LinkedIn, coordinating interview slots", "INR 10,000 - 14,000 /month", "3 months"),
    ("UI/UX Design Intern", "Figma wireframes, component design, portfolio review required", "INR 12,000 - 20,000 /month", "3-6 months"),
    ("Business Development Intern", "Lead generation, LinkedIn outreach, cold emails", "INR 10,000 - 15,000 /month + performance bonus", "2-4 months"),
    ("Content & Technical Writing Intern", "Writing technical guides, product documentation, blog posts", "INR 10,000 - 16,000 /month", "3 months"),
    ("Operations Intern", "Data verification, partner onboarding, customer issue resolution", "INR 10,000 - 15,000 /month", "3 months")
]

# Legitimate Companies, Domains, Portals
LEGIT_COMPANIES = [
    ("Zeta Analytics Pvt Ltd", "zetaanalytics.com", "https://careers.zetaanalytics.com/jobs"),
    ("HyperScale Technologies", "hyperscale.tech", "https://jobs.lever.co/hyperscale-tech"),
    ("RazorEdge Labs India", "razoredgelabs.io", "https://boards.greenhouse.io/razoredge"),
    ("NovaFin Services India", "novafin.in", "https://novafin.in/careers"),
    ("CloudVerve Systems", "cloudverve.com", "https://cloudverve.freshteam.com/jobs"),
    ("QuantumByte Solutions", "quantumbyte.co", "https://careers.quantumbyte.co"),
    ("NexGen Mobility Solutions", "nexgenmobility.in", "https://nexgenmobility.in/careers"),
    ("Aegis Healthtech India", "aegishealth.io", "https://jobs.ashbyhq.com/aegishealth"),
    ("InnoWave Software Labs", "innowavesoftware.com", "https://innowave.recruitee.com"),
    ("PulseRetail India Ltd", "pulseretail.in", "https://pulseretail.in/work-with-us"),
    ("FinEdge Capital Advisors", "finedgecapital.com", "https://careers.finedgecapital.com"),
    ("BlueDot Logistics India", "bluedotlogistics.in", "https://bluedotlogistics.in/careers"),
    ("Apex Infotech Solutions", "apexinfotech.co.in", "https://apexinfotech.co.in/current-openings"),
    ("Vortex Media Labs", "vortexmedia.in", "https://jobs.lever.co/vortexmedialabs"),
    ("Skyline Infosec India", "skylineinfosec.com", "https://boards.greenhouse.io/skylineinfosec"),
    ("Zenith Edutech India", "zenithedutech.com", "https://zenithedutech.com/join-us"),
    ("Crestview Partners India", "crestview.co.in", "https://crestview.co.in/careers"),
    ("UrbanTech Automations", "urbantech.in", "https://urbantech.in/careers"),
    ("SimpliLogix Solutions", "simplilogix.com", "https://simplilogix.keka.com/careers"),
    ("OmniCloud Innovations", "omnicloud.io", "https://jobs.lever.co/omnicloud")
]

REAL_EXPLANATIONS = [
    "Classification: Real. Red Flags: None. The posting follows professional standards with an official domain-based portal link.",
    "Classification: Real. Red Flags: None. The post is professional, specifies stipend/salary range, and uses legitimate procedures.",
    "Classification: Real. Red Flags: None. The organization is a typical corporate structure, and the communication follows standard hiring patterns.",
    "Classification: Real. Red Flags: None. The posting is standard, specifies the location, role, and salary, and guides users to an official application route.",
    "Classification: Real. Red Flags: None. The posting outlines a standard recruitment process.",
    "Classification: Real. Red Flags: None. The job requirements and application portal are standard for this level of role.",
    "Classification: Real. Red Flags: None. The criteria for candidates are logical, and the stipend is realistic for an internship.",
    "Classification: Real. Red Flags: None. Reputable company and standard professional application process.",
    "Classification: Real. Red Flags: None. Uses official career portal.",
    "Classification: Real. Red Flags: None. Formal application process described.",
    "Classification: Real. Red Flags: None. Transparent job terms on recognized platform."
]

TARGET_BRANDS = [
    "Amazon India", "Flipkart", "TCS (Tata Consultancy Services)", "Infosys", "Wipro",
    "HDFC Bank", "ICICI Bank", "Google India", "Microsoft India", "Reliance Jio",
    "Swiggy", "Zomato", "Myntra", "Airtel", "Tata Motors", "Deloitte India", "Tech Mahindra",
    "Indigo Airlines", "Air India", "Accenture India", "Paytm", "Cognizant", "L&T Infotech",
    "Maruti Suzuki", "Blinkit", "Zepto", "HCL Tech", "Mahindra & Mahindra"
]

FAKE_EMAILS = [
    "hr-recruitment-desk@gmail.com", "career.support2024@gmail.com", "hdfc-recruiter-desk@protonmail.com",
    "amazon-hiring-hub@outlook.com", "tcs-virtual-onboarding@yahoo.com", "infosys.careers.india@gmail.com",
    "recruiter.wiproindia@gmail.com", "flipkart.supplychain.desk@proton.me", "airindia.groundstaff.careers@gmail.com",
    "jio-telecom-hr@outlook.com", "google-remote-hiring@mail.com", "recruitment-desk-indigo@yahoo.com",
    "hr.tata-group-careers@rediffmail.com", "deloitte-hr-desk@gmail.com", "swiggy-vendor-jobs@protonmail.com",
    "zepto-hiring-desk@yahoo.com", "accenture.india.hiring@gmail.com", "blinkit.careers.portal@outlook.com",
    "internships@skillinfytech.com", "no-reply@propeers.in", "student@mail.internshala.com"
]

FAKE_URLS = [
    "bit.ly/tcs-direct-offer", "tinyurl.com/amazon-wfh-job", "tcs-careers-portal.in/register",
    "amazon-jobs-india.xyz/apply", "hdfc-careers-desk.online/login", "flipkart-hiring2024.site",
    "forms.gle/9xJ82kLaPqZ81", "t.me/Official_HR_Recruitment", "t.me/PartTime_Earnings_India",
    "wa.me/919876543210?text=ApplyJob", "t.me/AmazonReviewJobs", "internshala-direct-apply.cc",
    "naukri-job-portal.top", "indigo-airport-jobs.org/apply-form", "reliance-jio-hiring.in/apply",
    "t.me/OnlineTask_DailyPayout", "wa.me/918765432109?text=StartWork", "bit.ly/google-remote-2024",
    "https://skillinfytech.com/#apply-now", "https://propeers.in/bootcamps/software-developer-bootcamp",
    "https://link.internshala.com/v1/emailclick?q=eOFsDgg3oMLFoSxC3h"
]


def make_real_posting():
    cat = random.choice(["tech", "non_tech", "internship", "walkin", "referral"])
    company, domain, portal = random.choice(LEGIT_COMPANIES)
    city = random.choice(CITIES)
    
    if cat == "tech":
        role, skills, ctc, exp = random.choice(TECH_SPECS)
        skill_str = ", ".join(random.sample(skills, min(len(skills), random.randint(2, 4))))
        templates = [
            f"Job Posting: {company} is hiring a {role} in {city}. Required skills: {skill_str}. Experience: {exp}. CTC: {ctc}. Apply directly on our portal: {portal}.",
            f"Job Posting: Open position for {role} at {company} ({city} / Hybrid). Min {exp} experience with {skill_str}. Competitive salary ({ctc}). Send CV or apply at {portal}.",
            f"Job Posting: Hiring {role} @ {company}. Location: {city}. Tech stack: {skill_str}. Package: {ctc}. Interested candidates can submit resumes to careers@{domain}.",
            f"Job Posting: {role} required for {company} located in {city}. Must have hands-on experience in {skill_str}. Selection includes technical round + HR discussion. Apply via {portal}.",
            f"Job Posting: We are looking for a {role} to join our engineering team at {company}, {city}. Relevant experience: {exp}. Salary: {ctc}. Apply at careers@{domain}.",
            f"Job Posting: Urgent requirement: {role} at {company} ({city}). Key skills: {skill_str}. Experience: {exp}. Remuneration: {ctc}. Detailed JD and application at {portal}."
        ]
        text = random.choice(templates)
        
    elif cat == "non_tech":
        role, resp, ctc, exp = random.choice(NON_TECH_SPECS)
        templates = [
            f"Job Posting: {company} is looking for a {role} in {city}. Responsibilities: {resp}. Exp: {exp}. Salary: {ctc}. Apply via our careers page at {portal}.",
            f"Job Posting: Urgently hiring {role} for {company} in {city}. Role covers {resp}. CTC: {ctc}. Please send your updated resume to careers@{domain}.",
            f"Job Posting: {role} opening at {company} ({city}). Candidate must have {exp} experience. Offered salary: {ctc}. Register your application at {portal}.",
            f"Job Posting: Join {company} as a {role} ({city}). Key responsibilities include {resp}. Package: {ctc}. Official application link: {portal}."
        ]
        text = random.choice(templates)
        
    elif cat == "internship":
        role, req, stipend, duration = random.choice(INTERNSHIP_SPECS)
        templates = [
            f"Job Posting: {role} at {company} ({city} / Remote). Requirements: {req}. Duration: {duration}. Stipend: {stipend}. Apply on Internshala or via {portal}.",
            f"Job Posting: {company} is hiring a {role} for {duration} in {city}. Stipend: {stipend}. Looking for candidates proficient in {req}. Apply at {portal}.",
            f"Job Posting: Paid Internship: {role} at {company}. Stipend: {stipend}. Location: {city}. Pre-placement offer (PPO) based on performance. Send resume to hr@{domain}.",
            f"Job Posting: {role} opportunity at {company}. Duration: {duration}, Stipend: {stipend}. Requirements: {req}. Submit your profile on {portal}."
        ]
        text = random.choice(templates)
        
    elif cat == "walkin":
        role, _, ctc, exp = random.choice(NON_TECH_SPECS + [(r[0], "", r[2], r[3]) for r in TECH_SPECS[:6]])
        address = f"Building {random.randint(1,12)}, Mindspace IT Park, Sector {random.randint(10,65)}, {city}"
        templates = [
            f"Job Posting: Walk-in drive for {role} at {company}. Location: {address}. Experience: {exp}. Salary: {ctc}. Date: Saturday 10 AM to 4 PM. Bring 2 copies of resume and ID proof.",
            f"Job Posting: Mega Walk-in interview at {company} office ({address}) for {role}. Exp: {exp}. Offered CTC: {ctc}. Candidates must bring updated CV. No registration charges.",
            f"Job Posting: Direct Walk-in Interview for {role} at {company}, {city}. Office Address: {address}. Timing: 10:00 AM onwards. Standard HR and managerial evaluation rounds."
        ]
        text = random.choice(templates)
        
    else: # referral / ATS direct
        role, skills, ctc, exp = random.choice(TECH_SPECS)
        skill_str = ", ".join(random.sample(skills, 2))
        templates = [
            f"Job Posting: Direct opening: {role} at {company} ({city}). Tech: {skill_str}. Package: {ctc}. Send your profile to recruitment@{domain} or apply at {portal}.",
            f"Job Posting: Full-time {role} opening at {company} ({city} / Hybrid). Exp: {exp}. Tech: {skill_str}. Salary: {ctc}. Apply via our official careers board: {portal}."
        ]
        text = random.choice(templates)
        
    return {
        "system": SYSTEM_PROMPT,
        "user": text,
        "assistant": random.choice(REAL_EXPLANATIONS)
    }


def make_fake_posting():
    scam_type = random.choice([
        "micro_fee_internship", "bootcamp_marketing_spam", "course_upsell_scam",
        "campus_ambassador_bait", "free_trial_bait", "advance_fee", "telegram_task",
        "brand_spoof", "training_cert", "no_interview_high_salary", "data_entry_captive",
        "visa_airport", "personal_bank_harvest", "fake_govt_scam"
    ])
    
    brand = random.choice(TARGET_BRANDS)
    fake_email = random.choice(FAKE_EMAILS)
    fake_url = random.choice(FAKE_URLS)
    city = random.choice(CITIES)
    
    # 1. MICRO-FEE INTERNSHIP / DIGITAL ID CARD SCAM (SkillInfyTech archetype)
    if scam_type == "micro_fee_internship":
        fee = random.choice([89, 99, 149, 199, 249, 299, 399, 499])
        comp = random.choice(["SkillInfyTech IT Solutions", "CodeCraft Edutech", "NextGen Infotech Pvt Ltd", "ProSkills Tech Solutions", "AlphaTech Innovations"])
        duration = random.choice(["4-Weeks", "6-Weeks", "1-Month", "8-Weeks"])
        templates = [
            (f"Dear Candidate, Greetings from {comp} Private Limited. You are receiving this email because you showed interest in internship opportunities. We would like to inform you about our {duration} Internship Program. About {comp}: registered organization under MCA, recognized under MSME, aligned with AICTE academic internship guidelines. Program Details: Duration: {duration}. Internship Fee: No internship fee. Access Fee: ₹{fee} only (for Digital ID Card & platform access). Please note: The ₹{fee} amount is not an internship fee. It is charged only for Digital ID Card issuance, project access, LMS portal and certificate issuance. Application Link: {fake_url}. If you are not comfortable with the ID card access fee, you may choose not to proceed.",
             "Classification: Fake. Red Flags: Micro-fee access charge / Digital ID card fee trap; Deceptive 'No internship fee' disclaimer; False regulatory accreditation claims (MCA/MSME/AICTE)."),
            (f"Internship Offer: 4-Weeks Virtual Web Development Internship at {comp}. Zero tuition fee. Mandatory Digital ID card generation charge: ₹{fee} only. Certified under MSME & AICTE norms. Complete tasks to get Offer Letter & Letter of Recommendation. Pay ₹{fee} at {fake_url} to generate ID badge.",
             "Classification: Fake. Red Flags: Asks for ID card / platform access fee; Deceptive unpaid virtual internship; False regulatory accreditation."),
            (f"Selected for {duration} Data Science Internship at {comp}! There is NO training fee. However, candidates must pay a nominal access & verification fee of ₹{fee} for LMS server access and digital certificate issuance. Pay via UPI to activate your dashboard at {fake_url}.",
             "Classification: Fake. Red Flags: Asks for platform access fee; Hidden onboarding charges; Suspicious registration link.")
        ]
        text, resp = random.choice(templates)

    # 2. BOOTCAMP MARKETING SPAM / FAKE URGENCY (ProPeers MAANG archetype)
    elif scam_type == "bootcamp_marketing_spam":
        discount = random.choice(["40%", "50%", "60%", "70%"])
        coupon = random.choice(["MAANG", "FAANG40", "SUPER50", "DISCOUNT60", "CAREER40"])
        templates = [
            (f"Subject: MAANG Bootcamp @ Lowest Price. Final Call: Extra {discount} OFF Coupon {coupon}. Hi Candidate, this is your last chance to grab the DSA + System Design + AI Bootcamp at the lowest price it will ever be. FINAL HOURS: Biggest Discount We've Ever Offered. Use Code: {coupon}. Offer Ends @ 11:59 PM. Secure Your Seat Now at {fake_url}. 120+ Hours Live Sessions, FAANG Mock Interviews, Job Assistance & Profile Optimization. Once this window closes, the price goes back up.",
             "Classification: Fake. Red Flags: Aggressive marketing spam disguised as career opportunity; Fake urgency / countdown timer pressure; Exaggerated job placement guarantees."),
            (f"Final Hours: 60% OFF Full Stack Job Guarantee Bootcamp! Use coupon CODE: {coupon} before 11:59 PM tonight. Guaranteed interview calls at top product companies. Secure your seat at {fake_url} before price increases.",
             "Classification: Fake. Red Flags: Commercial course marketing spam; Unrealistic job placement claims; High pressure sales urgency.")
        ]
        text, resp = random.choice(templates)

    # 3. COURSE UPSELL DISGUISED AS APPLICATION UPDATE (upGrad / Internshala archetype)
    elif scam_type == "course_upsell_scam":
        course_fee = random.choice(["₹91,000 + taxes", "₹75,000", "₹1,20,000", "₹65,000 + GST"])
        templates = [
            (f"Subject: Update: You've a new update on Full Stack Development classroom program. Hello Candidate, Give your Full Stack skills the hands-on experience they need. With classroom training program, get placement application support & 3-year access to the career portal. Earn certificates from top corporate partners. Course fee: Starting from {course_fee}. Merit-based scholarship available for eligible students. Ready to kick-start your journey? Talk to a counsellor at {fake_url}.",
             "Classification: Fake. Red Flags: Expensive paid course upselling disguised as career notification; Deceptive marketing funnel; Aggressive tele-counsellor lead capture."),
            (f"Notification: Application Update on Data Engineering Master Program. Guaranteed placement support with 15 LPA CTC. Course enrollment fee: {course_fee}. Click to talk to our career counsellor and claim scholarship: {fake_url}.",
             "Classification: Fake. Red Flags: Expensive commercial course disguised as job application update; Exaggerated salary promises.")
        ]
        text, resp = random.choice(templates)

    # 4. CAMPUS AMBASSADOR / UNSOLICITED APPLICATION ACCEPTANCE
    elif scam_type == "campus_ambassador_bait":
        templates = [
            (f"Subject: [Update] Your application has been accepted. We'd love to have you represent our company at your campus! As a student, you're uniquely positioned to promote our programs and earn certificates and rewards. Learn more and accept your role at {fake_url}.",
             "Classification: Fake. Red Flags: Unsolicited acceptance notification; Unpaid student ambassador marketing scheme; Deceptive application confirmation."),
            (f"[Update] Congratulations! Your application for Campus Ambassador Lead has been approved. Lead promotional drives in your college to unlock goodies and completion certificate. Click here to confirm: {fake_url}.",
             "Classification: Fake. Red Flags: Unsolicited role assignment; Unpaid promotional labor disguised as prestigious campus leadership.")
        ]
        text, resp = random.choice(templates)

    # 5. FREE TRIAL BAIT & SWITCH
    elif scam_type == "free_trial_bait":
        templates = [
            (f"Subject: Get Your FREE Session Now. Hey Candidate, Still wondering if mentorship is worth it? Claim your Free 1:1 Trial Session with a real industry expert. Career roadmap, resume feedback, and mock interview prep. Only a few trial slots are left — and they're going fast. Claim Your Free Trial Session Now at {fake_url}.",
             "Classification: Fake. Red Flags: High pressure sales funnel; Fake scarcity ('slots going fast'); Lead generation marketing spam.")
        ]
        text, resp = random.choice(templates)

    # 6. ADVANCE FEE SCAMS
    elif scam_type == "advance_fee":
        fee = random.choice([350, 499, 750, 999, 1200, 1500, 1999, 2500, 3500])
        reason = random.choice([
            "refundable laptop security deposit", "ID card badge & document verification charges",
            "uniform procurement & gate pass fee", "courier charges for home office kit",
            "mandatory registration & onboarding processing charge", "interview seat reservation fee",
            "medical fitness checkup deposit", "company background verification processing fee"
        ])
        salary = random.choice(["45,000/month", "60k monthly", "12 LPA", "50,000 per month", "8.5 LPA", "70,000/month"])
        templates = [
            (f"Job Posting: We are hiring Remote Executives for {brand}. Salary {salary}. Transfer {fee} INR as {reason} to get official appointment letter immediately.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Suspicious, non-official registration link."),
            (f"Job Posting: Work from home Back Office Executive. Salary {salary}. Pay ₹{fee} for {reason} to confirm your joining. Contact HR on WhatsApp.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; High pressure to initiate via private communication channel."),
            (f"Job Posting: Direct hiring in {brand} for {city} branch. Guaranteed salary {salary}. Candidates must submit ₹{fee} towards {reason} before interview.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Guaranteed job offer without proper evaluation."),
            (f"Job Posting: Urgently required Document Verification Specialist. Pay: {salary}. Pay Rs {fee} {reason} via GooglePay/PhonePe to secure your employee code.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Suspicious request for personal financial transactions; Urgent hiring pressure.")
        ]
        text, resp = random.choice(templates)

    # 7. TELEGRAM / WHATSAPP TASK SCAMS
    elif scam_type == "telegram_task":
        daily_pay = random.choice(["2,500 - 5,000 daily", "3000 to 8000 INR per day", "1500 per 30 minutes", "5000 daily payout", "2000-4000/day"])
        task_desc = random.choice([
            "liking YouTube videos and subscribing", "rating 5-star reviews for hotels on Google Maps",
            "submitting screenshot tasks of merchant apps", "completing simple crypto affiliate click tasks",
            "watching promotional movie trailers and rating them"
        ])
        templates = [
            (f"Job Posting: Part-time online job for students and housewives. Earn {daily_pay} by just {task_desc}. No experience needed. Join Telegram channel {fake_url} to start now.",
             "Classification: Fake. Red Flags: Unrealistically high daily wage; Suspicious hiring channel (Telegram); Unrealistically high promise for low skill requirement."),
            (f"Job Posting: Work from home daily payout! Earn {daily_pay} from your smartphone. Task: {task_desc}. Instant UPI payout after each task. Contact @manager on Telegram.",
             "Classification: Fake. Red Flags: Unrealistically high daily wage; Suspicious hiring channel (Telegram); Vague, suspicious organization details.")
        ]
        text, resp = random.choice(templates)

    # 8. BRAND SPOOF
    elif scam_type == "brand_spoof":
        role = random.choice(["Assistant Manager", "Operations Executive", "Branch Coordinator", "Software Associate"])
        salary = random.choice(["8-12 LPA", "55,000/month", "7.5 LPA", "60k per month"])
        templates = [
            (f"Job Posting: Urgent opening for {role} at {brand} in {city}. CTC: {salary}. Send your resume to {fake_email}. Offer letter released within 24 hours without interview.",
             "Classification: Fake. Red Flags: Unknown organization email; Suspicious organization domain; No interview required / guaranteed job offer."),
            (f"Job Posting: Career opportunity at {brand}. Role: {role}, Location: {city}. Package: {salary}. Email CV to {fake_email}. Pay ₹800 for online test link.",
             "Classification: Fake. Red Flags: Unknown organization email; Asks for registration fee, security deposit, or any payment; Brand impersonation.")
        ]
        text, resp = random.choice(templates)

    # 9. TRAINING CERTIFICATION FEE SCAM
    elif scam_type == "training_cert":
        cert_fee = random.choice([1500, 1999, 2499, 3000, 4500, 5000])
        role = random.choice(["Data Analyst Trainee", "Python Developer Intern", "Digital Marketing Specialist"])
        salary = random.choice(["6 LPA", "8.5 LPA", "40k/month", "50,000 INR monthly"])
        templates = [
            (f"Job Posting: Guaranteed placement as {role} at MNC. Package {salary}. Must purchase mandatory ISO certified training module for ₹{cert_fee} to get final offer.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Guaranteed job offer conditional on paid purchase."),
            (f"Job Posting: Full Stack Developer Job Assurance Program with {brand}. Guaranteed 6 LPA salary post completion of ₹{cert_fee} training registration.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Guaranteed job offer; Brand impersonation.")
        ]
        text, resp = random.choice(templates)

    # 10. NO INTERVIEW HIGH SALARY
    elif scam_type == "no_interview_high_salary":
        role = random.choice(["Data Entry Typist", "Email Processing Assistant", "SMS Dispatcher", "Online Form Filler"])
        salary = random.choice(["75,000 per month", "80k monthly", "15 LPA", "20,000 per week"])
        templates = [
            (f"Job Posting: Simple MS Word typing job from home. Earn {salary}. No qualifications needed, 10th pass eligible. Immediate joining without any interview. Apply at {fake_url}.",
             "Classification: Fake. Red Flags: Unrealistically high salary; No interview required; Unrealistically high promise for low skill requirement."),
            (f"Job Posting: Need {role} immediately. Earn {salary} working just 2 hours a day from mobile. Instant offer letter upon registration on {fake_url}.",
             "Classification: Fake. Red Flags: Unrealistically high salary; No interview required / guaranteed job offer; Suspicious, non-official registration link.")
        ]
        text, resp = random.choice(templates)

    # 11. DATA ENTRY CAPTIVE / PENALTY TRAP
    elif scam_type == "data_entry_captive":
        deposit = random.choice([1000, 1500, 2000, 2500])
        penalty = random.choice(["5,000 INR", "10,000 INR", "legal notice", "court action"])
        templates = [
            (f"Job Posting: Offline Notepad data entry projects. Earn 30,000 per week. Refundable software license fee ₹{deposit} required. Accuracy penalty of {penalty} applies if QC fails.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Predatory agreement terms; Unrealistically high salary.")
        ]
        text, resp = random.choice(templates)

    # 12. VISA & AIRPORT SCAMS
    elif scam_type == "visa_airport":
        fee = random.choice([2500, 3500, 5000, 7500])
        templates = [
            (f"Job Posting: Urgent vacancies for Airport Ground Staff & Cargo Loader at {city} Airport. Salary 38,000 + food + accommodation. Pay ₹{fee} for airport security pass.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; No formal aviation recruitment channel; Urgent hiring pressure.")
        ]
        text, resp = random.choice(templates)

    # 13. PERSONAL / BANK HARVESTING
    elif scam_type == "personal_bank_harvest":
        templates = [
            (f"Job Posting: Selected for Back Office Executive role at {brand}. To release your salary account and joining kit, reply with Aadhaar, PAN, Netbanking credentials and OTP.",
             "Classification: Fake. Red Flags: Suspicious request for personal financial information; Urgent hiring pressure; No proper verification process.")
        ]
        text, resp = random.choice(templates)

    # 14. FAKE GOVT SCAM
    else:
        fee = random.choice([450, 750, 1100, 1500])
        templates = [
            (f"Job Posting: Direct recruitment under Digital India project for Gramin Data Operator in {city}. Salary 32,000/month. Pay ₹{fee} for online application form at {fake_url}.",
             "Classification: Fake. Red Flags: Asks for registration fee, security deposit, or any payment; Suspicious, non-official registration link; False government affiliation.")
        ]
        text, resp = random.choice(templates)

    return {
        "system": SYSTEM_PROMPT,
        "user": text,
        "assistant": resp
    }


def generate_augmented_dataset(target_total=3200):
    orig_df = pd.read_parquet('original_train.parquet')
    print(f"Loaded original baseline dataset with {len(orig_df)} records.")
    
    orig_df['system'] = SYSTEM_PROMPT
    
    existing_users = set(orig_df['user'].str.strip().str.lower().tolist())
    records = orig_df.to_dict('records')
    
    num_to_add = target_total - len(records)
    print(f"Generating {num_to_add} new diverse records...")
    
    # 60% fake (including new micro-fee & marketing archetypes), 40% real
    fake_target = int(num_to_add * 0.60)
    real_target = num_to_add - fake_target
    
    new_records = []
    
    # Generate Fake records
    added_fake = 0
    attempts = 0
    while added_fake < fake_target and attempts < fake_target * 25:
        attempts += 1
        item = make_fake_posting()
        key = item['user'].strip().lower()
        if key not in existing_users:
            existing_users.add(key)
            new_records.append(item)
            added_fake += 1

    # Generate Real records
    added_real = 0
    attempts = 0
    while added_real < real_target and attempts < real_target * 25:
        attempts += 1
        item = make_real_posting()
        key = item['user'].strip().lower()
        if key not in existing_users:
            existing_users.add(key)
            new_records.append(item)
            added_real += 1
            
    print(f"Generated {added_fake} new fake records and {added_real} new real records.")
    
    combined_records = records + new_records
    random.shuffle(combined_records)
    
    df_augmented = pd.DataFrame(combined_records)
    
    # Drop any duplicate user prompts
    df_augmented = df_augmented.drop_duplicates(subset=['user']).reset_index(drop=True)
    
    # Save outputs in multiple standard formats
    df_augmented.to_parquet('smolified_fakejob_expanded.parquet', index=False)
    df_augmented.to_csv('smolified_fakejob_expanded.csv', index=False)
    df_augmented.to_json('smolified_fakejob_expanded.jsonl', orient='records', lines=True)
    
    print(f"Successfully saved expanded dataset with {len(df_augmented)} total records!")
    return df_augmented


if __name__ == '__main__':
    df = generate_augmented_dataset(target_total=3200)
    print("\n--- Summary Statistics ---")
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    fake_cnt = df['assistant'].str.startswith('Classification: Fake').sum()
    real_cnt = df['assistant'].str.startswith('Classification: Real').sum()
    print(f"Fake count: {fake_cnt} ({fake_cnt/len(df)*100:.1f}%)")
    print(f"Real count: {real_cnt} ({real_cnt/len(df)*100:.1f}%)")
