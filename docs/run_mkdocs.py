import glob
import os
import shutil
from sys import argv

"""
README
------

Execute run_mkdocs.py from this directory to update the documentation. 
Default behavior is to build the documentation but not deploy it.

Required software:
    mkdocs            (install with: pip install mkdocs)
    material theme    (install with: pip install mkdocs-material)

Optional arguments:
    --deploy        build documentation and deploy on pyfsi.github.io/coconut/, 
                    this requires admin rights on GitHub
    --preview X     build documentation and preview webpage of file X.md, 
                    if X is not supplied, README.md is shown
                    
Example:
    python run_mkdocs.py --preview mappers
"""

# check directory
if os.getcwd() != os.path.dirname(os.path.realpath(__file__)):
    raise SystemError('execute run_mkdcos.py from its directory')

# clean docs folder and add coconuts
os.chdir(os.path.dirname(os.path.realpath(__file__)))
shutil.rmtree('docs', ignore_errors=True)

os.mkdir('docs')
os.mkdir('docs/images')
os.mkdir('docs/assets')
os.mkdir('docs/assets/images')

shutil.copy('logo.png', 'docs/images/logo.png')
shutil.copy('favicon.ico', 'docs/assets/images/favicon.ico')

# find all MarkDown files in CoCoNuT
files = glob.glob('../**/*.md', recursive=True)

# check for duplicate filenames
filenames = []
for file in files:
    filenames.append(file.split('/')[-1])

for i, filename in enumerate(filenames):
    if filenames.count(filename) > 1:
        print(f'WARNING - duplicate file "{files[i]}"')

# copy all MarkDown files to docs folder
for file in files:
    shutil.copy(file, 'docs/')

# check if all files are mentioned in nav
unused = []
used = False
for filename in filenames:
    with open('mkdocs.yml', 'r') as file:
        for line in file:
            if filename in line:
                used = True
                break
    if not used:
        unused.append(filename)
    used = False
for file in unused:
    print(f'WARNING - file "{file}" is not used in mkdocs.yml')



# build and deploy website
if len(argv) > 1:
    if argv[1] == '--preview':
        os.system('mkdocs build --clean')
        cwd = os.getcwd()
        if len(argv) == 3:
            cmd = 'firefox ' + os.path.join(cwd, 'site', argv[2], 'index.html &')
        else:
            cmd = 'firefox ' + os.path.join(cwd, 'site', 'index.html &')
        os.system(cmd)
    elif argv[1] == '--deploy':
        os.system('mkdocs gh-deploy')
    else:
        os.system('mkdocs build')
else:
    os.system('mkdocs build')
