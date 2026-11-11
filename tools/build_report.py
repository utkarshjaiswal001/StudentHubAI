from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.section import WD_SECTION
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(r'D:\Student Hub ( PROJECT )')
OUT=ROOT/'docs'/'submission'/'StudentHubAI_Mini_Project_Report.docx'
QA=ROOT/'tools'
QA.mkdir(exist_ok=True)

# Draw a clean architecture figure for insertion into the report.
W,H=1500,520
im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
try:
    f=ImageFont.truetype('arial.ttf',30); fs=ImageFont.truetype('arial.ttf',23)
except Exception:
    f=ImageFont.load_default(); fs=f
navy='#17324D'; blue='#2D6A8A'; pale='#EAF2F6'; gray='#536270'
boxes=[(40,185,300,340,'Student','Browser interface'),(395,185,665,340,'Flask application','Routes and session logic'),(760,100,1030,245,'SQLite database','Accounts, notes, mentor'),(760,300,1030,445,'PDF storage','Uploads directory'),(1150,185,1460,340,'OpenAI Responses API','Optional mentor replies')]
for x1,y1,x2,y2,title,sub in boxes:
    d.rounded_rectangle((x1,y1,x2,y2),radius=22,fill=pale,outline=blue,width=4)
    bb=d.textbbox((0,0),title,font=f); d.text((x1+(x2-x1-(bb[2]-bb[0]))/2,y1+37),title,font=f,fill=navy)
    bb=d.textbbox((0,0),sub,font=fs); d.text((x1+(x2-x1-(bb[2]-bb[0]))/2,y1+95),sub,font=fs,fill=gray)
def arrow(p1,p2,label=None,labelxy=None):
    d.line([p1,p2],fill=navy,width=5)
    import math
    a=math.atan2(p2[1]-p1[1],p2[0]-p1[0]); L=18
    pts=[p2,(p2[0]-L*math.cos(a-.5),p2[1]-L*math.sin(a-.5)),(p2[0]-L*math.cos(a+.5),p2[1]-L*math.sin(a+.5))]
    d.polygon(pts,fill=navy)
    if label and labelxy: d.text(labelxy,label,font=fs,fill=gray)
arrow((300,260),(395,260),'HTTP',(320,220))
arrow((665,225),(760,175),'SQL',(690,175))
arrow((665,295),(760,370),'Files',(690,335))
arrow((665,260),(1150,260),'Opt-in request',(820,220))
d.text((440,35),'STUDENTHUB AI - HIGH-LEVEL ARCHITECTURE',font=f,fill=navy)
fig=QA/'architecture.png'; im.save(fig)

doc=Document()
sec=doc.sections[0]
sec.top_margin=Inches(.75); sec.bottom_margin=Inches(.7); sec.left_margin=Inches(.9); sec.right_margin=Inches(.85)
# Base styles
styles=doc.styles
normal=styles['Normal']; normal.font.name='Times New Roman'; normal.font.size=Pt(11); normal.font.color.rgb=RGBColor(25,25,25)
normal._element.rPr.rFonts.set(qn('w:ascii'),'Times New Roman'); normal._element.rPr.rFonts.set(qn('w:hAnsi'),'Times New Roman')
normal.paragraph_format.line_spacing=1.12; normal.paragraph_format.space_after=Pt(6)
for sname,size in [('Title',24),('Heading 1',16),('Heading 2',13),('Heading 3',11)]:
    st=styles[sname]; st.font.name='Times New Roman'; st.font.size=Pt(size); st.font.bold=True; st.font.color.rgb=RGBColor(0,0,0)
    st._element.rPr.rFonts.set(qn('w:ascii'),'Times New Roman'); st._element.rPr.rFonts.set(qn('w:hAnsi'),'Times New Roman')
    st.paragraph_format.keep_with_next=True
styles['Heading 1'].paragraph_format.space_before=Pt(10); styles['Heading 1'].paragraph_format.space_after=Pt(8)
# Footer with page number
foot=sec.footer.paragraphs[0]; foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=foot.add_run('StudentHub AI  |  Mini Project Report  |  '); r.font.name='Times New Roman'; r.font.size=Pt(9)
fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); foot._p.append(fld)

def centered(text,size=12,bold=False,after=6):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(after)
    r=p.add_run(text); r.bold=bold; r.font.name='Times New Roman'; r.font.size=Pt(size); return p

def para(text='',style=None,align=None):
    p=doc.add_paragraph(style=style)
    if align is not None: p.alignment=align
    p.add_run(text); return p

def heading(text,level=1): doc.add_heading(text,level=level)

def bullet(text):
    p=doc.add_paragraph(style='List Bullet'); p.add_run(text); p.paragraph_format.space_after=Pt(3); return p

def numbered(text):
    p=doc.add_paragraph(style='List Number'); p.add_run(text); return p

def table(headers,rows,widths=None):
    t=doc.add_table(rows=1,cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style='Table Grid'
    for i,h in enumerate(headers):
        c=t.rows[0].cells[i]; c.text=h; shade(c,'17324D');
        for run in c.paragraphs[0].runs: run.bold=True; run.font.color.rgb=RGBColor(255,255,255); run.font.size=Pt(9)
    for row in rows:
        cells=t.add_row().cells
        for i,val in enumerate(row):
            cells[i].text=val; cells[i].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cells[i].paragraphs:
                p.paragraph_format.space_after=Pt(2)
                for run in p.runs: run.font.size=Pt(9)
        if len(t.rows)%2==0:
            for c in cells: shade(c,'F0F4F7')
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Inches(w)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    return t

def shade(cell,fill):
    tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:fill'),fill); tcPr.append(shd)
    mar=OxmlElement('w:tcMar')
    for side,val in [('top','90'),('start','100'),('bottom','90'),('end','100')]:
        e=OxmlElement('w:'+side); e.set(qn('w:w'),val); e.set(qn('w:type'),'dxa'); mar.append(e)
    tcPr.append(mar)

# 1 Title page
for _ in range(2): doc.add_paragraph()
centered('MINI PROJECT REPORT',16,True,20)
centered('STUDENTHUB AI',27,True,14)
centered('A Student Learning and Career Support Web Application',15,False,30)
centered('Submitted in partial fulfilment of the requirements for the award of',12,False,6)
centered('Bachelor of Technology (B.Tech)',14,True,5)
centered('Galgotias College of Engineering and Technology',13,True,14)
centered('____________________________________________',12,True,20)
centered('Submitted by',12,False,4)
centered('Utkarsh Jaiswal',14,True,2)
centered('Roll Number: 2400970310205',11,False,14)
centered('Under the Guidance of',12,False,4)
centered('Dr. Shilpee Patil, Associate Professor',13,True,10)
centered('Department: ______________________________',11,False,10)
centered('Academic Year 2026-2027',12,True,4)
centered('Date: 5 November 2026',11,False,0)
doc.add_page_break()
# 2 Declaration
centered('DECLARATION',16,True,20)
para('I, Utkarsh Jaiswal (Roll Number 2400970310205), B.Tech student at Galgotias College of Engineering and Technology, declare that this mini project report titled “StudentHub AI” describes the design and implementation of a student support web application developed as an academic project. The description is based on the project source code and its accompanying setup and deployment notes. Any external references used are listed in the bibliography.')
para('I understand that the project and report must be reviewed by the institute and project guide before submission. Department details and signature fields can be completed before submission.')
for _ in range(4): doc.add_paragraph()
para('Place: ____________________')
para('Date: ____________________')
para('Signature of Student: ______________________________')
doc.add_page_break()
# 3 Certificate
centered('CERTIFICATE',16,True,20)
para('This is to certify that the mini project entitled “StudentHub AI: A Student Learning and Career Support Web Application” has been prepared by Utkarsh Jaiswal, Roll Number 2400970310205, under the guidance of Dr. Shilpee Patil, Associate Professor, in partial fulfilment of the requirements of the B.Tech programme at Galgotias College of Engineering and Technology during the academic year 2026-2027.')
para('To the best of my knowledge, this report presents the work carried out for the project and is suitable for submission to the department, subject to institutional review and completion of the particulars below.')
for _ in range(5): doc.add_paragraph()
para('Project Guide: Dr. Shilpee Patil')
para('Designation: Associate Professor')
para('Additional Faculty: Dr. Richa, Associate Professor')
para('Institute: Galgotias College of Engineering and Technology')
para('Department: _________________________________')
para('Signature: ____________________    Date: ____________________')
for _ in range(2): doc.add_paragraph()
para('Head of Department: __________________________    Seal: ____________________')
doc.add_page_break()
# 4 Abstract
centered('ABSTRACT',16,True,20)
para('StudentHub AI is a Flask-based web application that brings student study resources and career support into one interface. The current implementation provides user registration and sign-in with account settings, a student dashboard with a My notes shortcut, a course-organized library of AKTU study notes browsed by year, branch, semester, and subject, an owner Admin page for managing notes, issue reports, and password resets, PDF/PowerPoint upload and preview, locally generated Quick Help for common subject questions, and a saved-conversation Career Mentor. The mentor can optionally request a response from the OpenAI Responses API when the user has configured a server-side API key and explicitly opts to share the conversation. Without that configuration, messages can still be saved locally.')
para('The application uses SQLite for accounts, note metadata, mentor conversations, messages, and suggestions. PDF files are stored separately in an upload directory. The code includes input validation, password hashing, CSRF protection, login lockout after repeated wrong passwords, security headers, owner-only library management, authenticated routes for student-specific functions, a health endpoint, and an automated test suite of 47 tests. The project is designed for a small academic demonstration; production use would require operational monitoring, backups, data-protection review, and a suitable persistent hosting plan.')
para('Keywords: Flask, student portal, AKTU notes, SQLite, PDF library, career mentor, web application.')
doc.add_page_break()
# 5 Acknowledgement
centered('ACKNOWLEDGEMENT',16,True,20)
para('I would like to thank my project guide, Dr. Shilpee Patil, Associate Professor, Dr. Richa, Associate Professor, and the department for their guidance and support during the development of StudentHub AI. I am also grateful to the students whose learning and career-support needs informed the project features.')
para('I acknowledge the maintainers of Flask, SQLite, Werkzeug, and the other software libraries used by the application, together with the documentation referenced in this report. Their tools and documentation supported the implementation and deployment planning.')
para('I thank my family and friends for their encouragement throughout this work.')
for _ in range(5): doc.add_paragraph()
para('Utkarsh Jaiswal')
doc.add_page_break()
# 6 contents (static page references refreshed after final render if needed)
centered('CONTENTS',16,True,15)
rows=[('Declaration','2'),('Certificate','3'),('Abstract','4'),('Acknowledgement','5'),('List of Figures','7'),('List of Tables','8'),('1. Introduction','9'),('2. Requirements and Feasibility','10'),('3. System Design','11'),('4. Implementation','13'),('5. Security and Deployment','15'),('6. Conclusion and Future Scope','16'),('Bibliography','17')]
table(['Section','Page'],rows,[5.8,.8])
para('Page numbers refer to the beginning of each section in this report.',style=None)
doc.add_page_break()
# 7 list figures
centered('LIST OF FIGURES',16,True,18)
table(['Figure','Title','Page'],[('3.1','High-level system architecture','11')],[.9,4.8,.8])
doc.add_page_break()
# 8 list tables
centered('LIST OF TABLES',16,True,18)
table(['Table','Title','Page'],[('2.1','Functional requirements','10'),('2.2','Non-functional requirements','10'),('3.1','Core data entities','12'),('4.1','Application modules','14')],[.9,4.8,.8])
doc.add_page_break()
# Main chapters
heading('1. Introduction',1)
heading('1.1 Background',2)
para('Students often need to move between separate sources for course notes, short academic questions, and career guidance. StudentHub AI brings these activities together in a web application aimed at engineering students. Its public home page introduces the service, while authenticated users can access a dashboard, notes library, account centre, and mentor conversation history.')
heading('1.2 Problem Statement',2)
para('Study PDFs can be difficult to find when they are scattered across informal channels, and a single short question may need a different kind of support from a longer career-planning conversation. The project addresses these needs by combining a structured notes catalogue with a lightweight local help feature and an optional AI-backed mentor.')
heading('1.3 Objectives',2)
for x in ['Provide user accounts, account settings, and a personalized student dashboard.','Organize notes by year, branch, semester, and subject (1st year skips the semester step because subjects are common), with preview and download.','Give the library owner an Admin page to upload, edit, and delete notes, review issue reports, and reset student passwords.','Answer selected common subject questions locally and route longer requests into a saved mentor conversation.','Keep AI-provider access optional and controlled by server configuration and a user sharing choice.','Support a small demonstration deployment with persistent storage configured separately from application code.']: bullet(x)
heading('1.4 Scope and Limitations',2)
para('The implementation is a single Flask application backed by SQLite and file-system PDF storage. The note catalogue currently defines four academic years and a set of engineering branches. AI mentor responses depend on an external API key and network access; the project notes caution that some free hosting environments restrict outbound requests. The repository does not establish a production-scale deployment or institution-wide administration workflow.')
heading('2. Requirements and Feasibility',1)
heading('2.1 Functional Requirements',2)
table(['ID','Requirement'],[('FR-1','Register a student using profile details and a password; sign in and sign out.'),('FR-2','Show a dashboard and account centre; let students edit their profile, change their password, delete their account, and open their own notes directly.'),('FR-3','Browse notes by year, branch, semester, and subject; search subjects; highlight new uploads.'),('FR-4','Owner uploads valid PDF/PPTX notes with matching year and semester; edits or deletes them; students preview and download.'),('FR-5','Answer supported Quick Help questions locally and retain short session history.'),('FR-6','Save mentor conversations; call the configured AI provider only when enabled and requested.'),('FR-7','Accept issue reports, let the owner close them, and expose a health endpoint for database connectivity.'),('FR-8','Let the owner reset a forgotten student password with a temporary password that must be changed at next sign-in.')],[.7,5.9])
heading('2.2 Non-functional Requirements',2)
table(['Area','Implementation / expectation'],[('Security','Password hashes, CSRF tokens, login lockout, security headers, 7-day sessions, owner-only library management, secure filename handling, bounded upload size, and server-side secret configuration.'),('Privacy','AI sharing is optional. The provider call sends the new message and recent conversation context when the user selects the sharing option.'),('Maintainability','A compact Flask application, templates, SQLite schema initialization, environment configuration, and separate setup/deployment notes.'),('Availability','Suitable for a small demo with backups. Hosting limits and outbound-network restrictions affect AI and uptime.'),('Usability','Course-filtered browsing, inline PDF preview, and a progression from quick answers to longer mentor conversations.')],[1.2,5.4])
heading('2.3 Feasibility',2)
para('Technical feasibility is supported by a lightweight Python stack: Flask handles HTTP routes and rendering, SQLite stores structured records, and the file system stores PDFs. The local setup uses a Python virtual environment. The deployment guide proposes PythonAnywhere for a demonstration and explains that database and uploads should reside in persistent user storage. Economic feasibility depends on the hosting tier and any paid provider usage; AI replies are optional and may incur API charges. [1][2]')
heading('3. System Design',1)
heading('3.1 Architecture',2)
para('The browser communicates with Flask routes. Flask applies session and validation logic, reads or writes structured records in SQLite, and serves uploaded PDFs from the configured upload directory. The optional mentor integration sends a bounded recent conversation context to the OpenAI Responses API only when an API key is configured and the user has opted to share. [1]')
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(fig),width=Inches(6.25))
cap=doc.add_paragraph('Figure 3.1  High-level architecture of StudentHub AI'); cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
for r in cap.runs: r.italic=True; r.font.size=Pt(9)
heading('3.2 Data Design',2)
para('The database schema separates user identity, study-note metadata, note activity, mentor conversations and messages, and suggestions. Foreign keys link student-owned records and note activity to users, and mentor messages to conversations. Uploaded PDF bytes remain outside SQLite; each note row stores a generated storage name and the original display filename.')
table(['Entity','Purpose and key relationships'],[('users','Student profile and password hash; unique case-insensitive email.'),('study_notes','Course metadata and stored PDF filename; uploaded_by references users.'),('note_activity','Records preview/download events for a user and note.'),('mentor_conversations','Conversation owner, title, created and updated timestamps.'),('mentor_messages','User or assistant messages associated with one conversation.'),('suggestions','Issue report text, category, and open/closed status; optional user association.'),('login_attempts','Failed sign-in count and lock expiry per email, used for lockout.')],[1.6,5.0])
heading('3.3 Main Workflows',2)
numbered('A student registers or signs in; successful authentication establishes a session and opens the dashboard.')
numbered('A student chooses year, branch, and semester (1st year goes straight to subjects), or uses My notes to open their own branch and year. Upload processing checks metadata, year/semester consistency, file type, file signature, and size before recording the file.')
numbered('The owner manages the library from the Admin page: editing note details, deleting notes after a confirmation step, closing issue reports, and resetting student passwords.')
numbered('A short supported question is answered locally. A longer question can be promoted to a persistent mentor thread, preserving the earlier exchanges.')
numbered('When AI sharing is selected and a provider key is configured, the server requests an answer using recent messages and saves the response into the conversation.')
heading('4. Implementation',1)
heading('4.1 Technology Stack',2)
para('The server is implemented in Python with Flask. Jinja templates render the user interface, SQLite provides relational persistence, and Werkzeug supplies password hashing and safe filename utilities. The OpenAI Python SDK is imported only in the optional mentor path. Configuration values such as SECRET_KEY, DATABASE_PATH, UPLOAD_FOLDER, OPENAI_API_KEY, and OPENAI_MODEL are read from the environment. [1][3]')
heading('4.2 Application Modules',2)
table(['Module','Responsibilities'],[('Accounts and sessions','Registration, login, logout, session state, dashboard, and account details.'),('Quick Help','Local subject answers, note-search intent, limited session history, and hand-off to the full mentor.'),('Notes library','Year/branch/semester/subject browsing, subject search, New badges, PDF/PPTX upload, preview, download, and activity recording.'),('Admin tools','Owner-only notes list, edit and delete, issue report review, and student password reset.'),('Account settings','Edit profile, change password, delete account, and My notes shortcut.'),('Career Mentor','Authenticated saved conversations, messages, and optional API-backed replies.'),('Persistence and operations','SQLite schema, file storage configuration, error handling, and /health database check.')],[1.65,4.95])
heading('4.3 Validation and Error Handling',2)
para('Registration checks required fields, matching passwords, a minimum password length, and duplicate email addresses. Notes upload requires course metadata, a safe .pdf filename, a PDF signature, and a valid file within the configured 20 MB request limit. Mentor messages and suggestions have length limits. When the AI provider is missing or fails, the user message remains saved and the interface can report that no AI response was produced.')
heading('4.4 Testing',2)
para('The project includes an automated test suite (47 tests, Python unittest with Flask\'s test client) that runs against a temporary database. It covers safe redirects, CSRF protection, registration validation, owner-only access, the notes browsing flow, upload consistency rules, login lockout, security headers, admin note editing and deletion, issue reports, password reset and forced password change, profile editing, and account deletion. All tests pass.')
heading('5. Security and Deployment',1)
heading('5.1 Security Considerations',2)
para('Passwords are stored as hashes rather than plain text. Every form carries a CSRF token, logout accepts only POST requests, and redirects are limited to same-site paths. Sign-in locks for 15 minutes after five wrong passwords for the same email, and sessions expire after seven days. Every page sends X-Frame-Options, X-Content-Type-Options, and Referrer-Policy headers. Upload, edit, and delete actions require the single owner account, checked in the database on every request. Sensitive routes use a login-required wrapper, and queries constrain a mentor conversation to its owner. Uploaded filenames are sanitized for display and stored under generated unique names. Session-cookie flags include HttpOnly and SameSite=Lax; Secure can be enabled by environment configuration for HTTPS deployment. The application secret should be set to a stable random value in deployment and kept private. [1]')
para('The AI setup guide states that the API key is read by the server and is not rendered into the page. When sharing is enabled, the application sends the current message and recent conversation messages to the provider. Users should therefore avoid sharing sensitive personal information in those conversations. Provider calls may incur charges. [1][3]')
heading('5.2 Deployment Notes',2)
para('The deployment guide describes PythonAnywhere Beginner as a possible small-demo host and gives environment settings for a stable secret, persistent SQLite path, upload directory, and secure cookies. It warns that the free service has resource and expiry limits and may restrict outbound internet access. The local SQLite database and PDFs do not automatically migrate to a hosted deployment; any migration should be intentional and backed up. [2]')
heading('5.3 Operational Checklist',2)
for x in ['Set a stable random SECRET_KEY and HTTPS cookie setting in the hosting environment.','Place the SQLite database and uploaded PDFs in persistent storage; back them up.','Keep .env, local instance data, and uploaded study files out of public source control.','Confirm registration, login/logout, notes browsing, upload, preview, and health check after deployment.','Enable AI only after reviewing provider access, privacy expectations, network access, and API costs.']: bullet(x)
heading('6. Conclusion and Future Scope',1)
para('StudentHub AI combines a student account area, an organized notes library, local Quick Help, and an optional saved AI Career Mentor in one Flask application. Its lightweight SQLite and file-storage design supports local use and a small academic demonstration. The project documentation also identifies practical deployment constraints, especially persistence, backups, free-tier limits, and outbound API access.')
heading('6.1 Future Scope',2)
for x in ['Connect the AI Career Mentor to a free-tier AI provider, with Quick Help as an offline fallback.','Add email-based password reset when hosting allows outbound email.','Search inside note PDFs and show matching pages.','Add automated backup and restore tools for SQLite data and PDF uploads.','Improve accessibility and mobile usability through structured UI audits and user feedback.','Add deployment monitoring and explicit retention controls for account and mentor data.','Evaluate alternative hosting and AI-provider options against cost, privacy, and reliability needs.']: bullet(x)
heading('Bibliography',1)
refs=[
'[1] StudentHub AI project source and configuration notes: app.py, AI_SETUP.md, and templates/, local project files, accessed 5 November 2026.',
'[2] StudentHub AI, “Free Flask deployment for StudentHub AI,” DEPLOYMENT.md, local project documentation, accessed 5 November 2026.',
'[3] OpenAI, “Responses API,” API reference, https://platform.openai.com/docs/api-reference/responses, accessed 5 November 2026.',
'[4] Pallets Projects, “Flask Documentation,” https://flask.palletsprojects.com/, accessed 5 November 2026.',
'[5] SQLite, “SQLite Documentation,” https://www.sqlite.org/docs.html, accessed 5 November 2026.',
'[6] Werkzeug, “Utilities,” https://werkzeug.palletsprojects.com/, accessed 5 November 2026.'
]
for x in refs: para(x)

# Keep heading widow/orphan and identify document metadata.
doc.core_properties.title='StudentHub AI Mini Project Report'
doc.core_properties.subject='Student learning and career support web application'
doc.core_properties.author='Utkarsh Jaiswal'
doc.save(OUT)
print(OUT)

