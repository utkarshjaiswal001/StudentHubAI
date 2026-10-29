from pathlib import Path
p=Path(r'.studenthub-build/build_report.py')
s=p.read_text(encoding='utf-8')
replacements={
"centered('Submitted in partial fulfilment of the requirements for the award of',12,False,6)":"centered('Submitted in partial fulfilment of the requirements for the award of',12,False,6)\ncentered('Bachelor of Technology (B.Tech)',14,True,5)\ncentered('Galgotias College of Engineering and Technology',13,True,14)",
"centered('Roll Number: ____________________',11,False,14)":"centered('Roll Number: 2400970310205',11,False,14)",
"I, Utkarsh Jaiswal, declare that this mini project report titled “StudentHub AI” describes":"I, Utkarsh Jaiswal (Roll Number 2400970310205), B.Tech student at Galgotias College of Engineering and Technology, declare that this mini project report titled “StudentHub AI” describes",
"Roll Number ____________________, under my guidance and supervision, in partial fulfilment of the requirements of ______________________________ during":"Roll Number 2400970310205, under the guidance of Dr. Shilpee Patil, Associate Professor, in partial fulfilment of the requirements of the B.Tech programme at Galgotias College of Engineering and Technology during",
"para('Project Guide: ______________________________')":"para('Project Guide: Dr. Shilpee Patil')",
"para('Designation: _________________________________')":"para('Designation: Associate Professor')\npara('Additional Faculty: Dr. Richa, Associate Professor')",
"para('Department / Institute: ________________________')":"para('Institute: Galgotias College of Engineering and Technology')\npara('Department: _________________________________')",
"para('Head of Department: __________________________    Seal: ____________________')":"para('Head of Department: __________________________    Seal: ____________________')",
"para('I would like to thank my project guide and department for their guidance and support during the development of StudentHub AI.":"para('I would like to thank my project guide, Dr. Shilpee Patil, Associate Professor, Dr. Richa, Associate Professor, and the department for their guidance and support during the development of StudentHub AI.",
}
for old,new in replacements.items():
    if old not in s: raise SystemExit('Missing expected source text: '+old[:100])
    s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
