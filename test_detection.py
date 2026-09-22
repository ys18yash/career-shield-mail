import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from ml.explain import ModelExplainer

explainer = ModelExplainer()

emails = {
    "SkillInfyTech ₹89 ID Fee Fake Internship": """Dear Candidate , Greetings from SkillInfyTech IT Solutions Private Limited . You are receiving this email because you have previously shown interest in our organization and internship opportunities . Based on this , we would like to inform you about our 4 - Weeks Internship Program , designed to provide practical industry exposure through structured , project - based learning . About SkillInfyTech IT Solutions : SkillInfyTech IT Solutions Private Limited is a registered organization under MCA , recognized under MSME , and aligned with AICTE academic internship guidelines . All internship activities are conducted in accordance with standard organizational and professional practices . About the Internship : This internship focuses on hands - on , real - world projects , helping participants strengthen their resumes with verified , industry - aligned experience under guided mentorship . Program Details : • Duration : 4 Weeks • Internship Fee : No internship fee • Access Fee : ₹ 89 only ( for Digital ID Card & platform access ) ✅ Program Highlights Duration : 4 Weeks Project - based learning approach Mentor - guided task execution Internship Completion Certificate Letter of Recommendation ( based on performance ) Resume and interview preparation support Internship Benefits : ✅ 𝗗𝗶𝗴𝗶𝘁𝗮𝗹 𝗜𝗗 | 𝗣𝗿𝗼𝗷𝗲𝗰𝘁𝘀 & 𝗤𝘂𝗶𝘇𝘇𝗲𝘀 | 𝗥𝗲𝗮𝗹 - 𝘄𝗼𝗿𝗹𝗱 𝗣𝗿𝗼𝗷𝗲𝗰𝘁𝘀 ✅ 𝗢𝗳𝗳𝗲𝗿 𝗟𝗲𝘁𝘁𝗲𝗿 & 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗶𝗼𝗻 𝗖𝗲𝗿𝘁𝗶𝗳𝗶𝗰𝗮𝘁𝗲 ✅ 𝗥𝗲𝘀𝘂𝗺𝗲 & 𝗟𝗶𝗻𝗸𝗲𝗱𝗜𝗻 𝘀𝘂𝗽𝗽𝗼𝗿𝘁 | 𝗖𝗮𝗿𝗲𝗲𝗿 𝗴𝘂𝗶𝗱𝗮𝗻𝗰𝗲 Please note : The ₹ 89 amount is not an internship fee . It is charged only for Digital ID Card issuance and access to projects , quizzes , and internship resources . Eligibility : • Students from any discipline • Recent graduates • Individuals seeking practical project experience Application Link : https : / / skillinfytech . com / # apply - now If you are not comfortable with the ID card access fee , you may choose not to proceed further . For any clarification , feel free to reply to this email . Regards , SkillInfyTech IT Solutions Private Limited Support Team""",
    
    "ProPeers MAANG Bootcamp Discount Urgency": """Hi Yash, This is your last chance to grab the DSA + System Design + AI Bootcamp at the lowest price it will ever be. FINAL HOURS: Biggest Discount We've Ever Offered Use Code: MAANG Extra 40% OFF Offer Ends @ 11:59 PM Secure Your Seat Now This is a comprehensive DSA & System Design + AI Bootcamp built for engineers targeting top product companies, and this is the lowest price it will ever be listed at. Inside the Bootcamp: 120+ Hours of Live Sessions 200+ DSA Problems (Pattern-Based Learning) System Design — Basics to Advanced Lifetime Access to Session Recordings Live Doubt-Clearing Sessions FAANG-Level Mock Interviews Job Assistance & Profile Optimization Certificates & Bootcamp Goodies Elite Learning Community & Peer Support Once this window closes, the price goes back up — and this offer won't return. Claim Your Spot at 40% OFF Parikh Jain Founder @ ProPeers""",

    "Internshala/upGrad ₹91k Classroom Upsell": """Hello Yash, Give your Full Stack skills the hands-on experience they need to stand out. With upGrad's classroom training program, take your Full Stack Development skills beyond tutorials with structured classroom learning, mentorship, hands-on projects & real-time doubt resolution. Build, practice, and strengthen the skills you need to take on real-world development challenges with confidence. Key Highlights 4–6 months classroom training in Bangalore Curriculum designed based on current industry & hiring trends for Full Stack, Java & React Developer roles Work on projects like Weather Forecast App, E-commerce Website, Social Connect (Facebook-like social platform) and more Free access to 10+ programming tools Masterclasses by industry professionals Get placement application support & 3-year access to the career portal Earn certificates from PwC, upGrad & NSDC Course fee: Starting from ₹91,000 + taxes Merit-based scholarship available for eligible students (T&C Apply) Ready to kick-start your full stack development journey? Talk to a counsellor. By clicking, you agree to receive a call from upGrad & agree to upGrad's privacy policy. Internshala (Scholiverse Educare Pvt. Ltd.)""",

    "Internshala Campus Ambassador Pitch": """Hi Yash, We'd love to have you represent Internshala at VTU. As a B.E student at VTU, you're uniquely positioned to help your peers discover valuable career opportunities while gaining exceptional experience for yourself. Here's what makes this special: Develop leadership and communication skills Exclusive access to masterclasses with industry experts Opportunity to earn recognition and rewards Build your professional network right from campus LEARN MORE ISP Team from Internshala""",

    "ProPeers Free Trial Session Bait": """Hey Yash, Still wondering if mentorship is worth it? How about finding out — for free? You still have a chance to claim your Free 1:1 Trial Session with a real industry expert. Whether it's DSA doubts, resume feedback, a career roadmap, or simply someone to guide you — this trial is built to give you clarity. Here's what you'll get: Career roadmap based on your goals Real-time project & resume feedback Mock interview prep tips from top mentors Clarity on what to do next Only a few trial slots are left — and they're going fast. Claim Your Free Trial Session Now""",

    "Legitimate Corporate Internship (Google Summer SWE)": """Dear Yash, Thank you for interviewing with Google for the Software Engineering Intern role in Bangalore. We were very impressed by your algorithmic problem solving and system design discussions. We are delighted to offer you a 12-week software engineering internship position with Google India. Offer Highlights: Role: Software Engineering Intern, Location: Bangalore (Hybrid), Monthly Stipend: INR 1,15,000 / month, Duration: May 2027 – August 2027. Benefits: Relocation assistance, wellness benefits, free meals, and guided mentorship under senior Staff Engineers. Your official offer letter and onboarding packet have been uploaded to your candidate portal on Google Careers (https://careers.google.com). Please review the formal documents and sign through DocuSign. Warm regards, Priya Sharma, University Staffing Specialist, Google India."""
}

print("=" * 65)
print("VERIFYING MODEL PREDICTIONS & EXPLANATIONS ACROSS ALL ARCHETYPES")
print("=" * 65)

for title, body in emails.items():
    res = explainer.explain(body, "Stacking Ensemble")
    status = "🚨 SPAM / FAKE" if res["is_spam"] else "✅ LEGITIMATE"
    print(f"\n[Scenario] {title}")
    print(f"  Result       : {status} ({res['threat_level']})")
    print(f"  Risk Prob    : {res['risk_score'] * 100:.1f}%")
    print(f"  Indicators   : {len(res['security_triggers'])} security triggers flagged")
    for trg in res["security_triggers"]:
        print(f"    - [{trg['severity']}] {trg['category']}: {trg['detail']}")
    
    consensus_str = ", ".join([f"{m}: {data['classification']} ({data['risk_score']*100:.0f}%)" for m, data in res["model_consensus"].items()])
    print(f"  Consensus    : {consensus_str}")

print("\n" + "=" * 65)
print("ALL TESTS COMPLETE")
