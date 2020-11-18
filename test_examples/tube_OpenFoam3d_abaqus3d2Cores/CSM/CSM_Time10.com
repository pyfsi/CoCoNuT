from driverConstants import *
from driverStandard import StandardAnalysis
import driverUtils, sys
options = {
    'SIMExt':'.sim',
    'abaquslm_license_file':'@bump.ugent.be',
    'ams':OFF,
    'analysisType':STANDARD,
    'applicationName':'analysis',
    'aqua':OFF,
    'ask_delete':OFF,
    'beamSectGen':OFF,
    'biorid':OFF,
    'cavityTypes':[],
    'cavparallel':OFF,
    'compile_fortran':['ifort', '-V', '-c', '-fPIC', '-auto', '-mP2OPT_hpo_vec_divbyzero=F', '-extend_source', '-fpp', '-WB', '-I%I', '-fpp', '-qopenmp'],
    'complexFrequency':OFF,
    'contact':OFF,
    'cosimulation':OFF,
    'coupledProcedure':OFF,
    'cpus':1,
    'cse':OFF,
    'cyclicSymmetryModel':OFF,
    'directCyclic':OFF,
    'direct_solver':DMP,
    'dsa':OFF,
    'dynamic':ON,
    'filPrt':[],
    'fils':[],
    'finitesliding':OFF,
    'foundation':OFF,
    'geostatic':OFF,
    'geotech':OFF,
    'heatTransfer':OFF,
    'importer':OFF,
    'importerParts':OFF,
    'includes':[],
    'initialConditionsFile':OFF,
    'input':'CSM_Restart',
    'inputFormat':INP,
    'interactive':None,
    'job':'CSM_Time10',
    'keyword_licenses':[],
    'lanczos':OFF,
    'libs':[],
    'link_exe':['g++', '-fPIC', '-Wl,-Bdynamic', '-o', '%J', '%F', '%M', '%L', '%B', '%O', '-lpthread', '-lm', '-lifcoremt', '-Xlinker -L/usr/lib64/'],
    'magnetostatic':OFF,
    'massDiffusion':OFF,
    'modifiedTet':OFF,
    'moldflowFiles':[],
    'moldflowMaterial':OFF,
    'mp_host_list':[['cfdclu27', 16]],
    'mp_mode':THREADS,
    'mp_mode_requested':THREADS,
    'multiphysics':OFF,
    'noDmpDirect':[],
    'noMultiHost':[],
    'noMultiHostElemLoop':[],
    'no_domain_check':1,
    'oldjob':'CSM_Time9',
    'outputKeywords':ON,
    'output_precision':FULL,
    'parameterized':OFF,
    'partsAndAssemblies':OFF,
    'parval':OFF,
    'postOutput':OFF,
    'preDecomposition':OFF,
    'restart':ON,
    'restartEndStep':False,
    'restartIncrement':0,
    'restartStep':0,
    'restartWrite':ON,
    'rezone':OFF,
    'runCalculator':OFF,
    'scratch':'/tmp/Tango20089/CSM/',
    'soils':OFF,
    'soliter':OFF,
    'solverTypes':['DIRECT'],
    'standard_parallel':ALL,
    'staticNonlinear':OFF,
    'steadyStateTransport':OFF,
    'step':ON,
    'subGen':OFF,
    'subGenLibs':[],
    'subGenTypes':[],
    'submodel':OFF,
    'substrLibDefs':OFF,
    'substructure':OFF,
    'symmetricModelGeneration':OFF,
    'thermal':OFF,
    'tmpdir':'/tmp/Tango20089/CSM',
    'tracer':OFF,
    'user':'usr.f',
    'usub_lib_dir':'/lusers/temp/mathieu/PycharmProjects/coconut/test_examples/tube_OpenFoam3d_abaqus3d2Cores/CSM/libusr/',
    'visco':OFF,
}
analysis = StandardAnalysis(options)
status = analysis.run()
sys.exit(status)
