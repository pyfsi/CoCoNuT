from part import *
from material import *
from section import *
from assembly import *
from step import *
from interaction import *
from load import *
from mesh import *
from job import *
from sketch import *
from visualization import *
from connectorBehavior import *
import importlib.util
import sys

coconut_path = importlib.util.find_spec('coconut').submodule_search_locations[0]
spec = importlib.util.spec_from_file_location('make_surface',
                                              coconut_path +
                                              '/coupling_components/solver_wrappers/abaqus/extra/make_surface.py')
module = importlib.util.module_from_spec(spec)
sys.modules['make_surface'] = module
spec.loader.exec_module(module)
from make_surface import *

e_modulus = 1e7
poisson_coefficient = 0.49
density = 1100.0
gravity = 9.81
delta_t = 0.001

mdb = Mdb(pathName='case_breaking_dam.cae')
beamModel = mdb.ModelFromInputFile(name='Model-1', inputFileName='mesh_breaking_dam.inp')
beamMaterial = beamModel.Material(name='Material');
beamMaterial.Elastic(table=((e_modulus, poisson_coefficient),))
beamMaterial.Density(table=((density,),))
beamAssembly = beamModel.rootAssembly
beamInstance = beamAssembly.instances['PART-1-1']
beamPart = beamModel.parts['PART-1']
beamModel.HomogeneousSolidSection(material='Material', name='BeamSection', thickness=1.0)
beamPart.SectionAssignment(offset=0.0, region=Region(elements=beamPart.elements), sectionName='BeamSection')
step1 = beamModel.ImplicitDynamicsStep(name='Step-1', previous='Initial', timePeriod=delta_t, nlgeom=ON,
                                       maxNumInc=1, haftol=0.1, initialInc=delta_t, minInc=delta_t, maxInc=delta_t,
                                       amplitude=RAMP, timeIncrementationMethod=FIXED, application=MODERATE_DISSIPATION)
step1.Restart(frequency=99999, overlay=ON)
beamInsideMoving0 = SurfaceFromNodeSet(beamAssembly, beamInstance, 'BEAMINSIDEMOVING0', 'BEAMINSIDEMOVING0')
beamInsideMoving1 = SurfaceFromNodeSet(beamAssembly, beamInstance, 'BEAMINSIDEMOVING1', 'BEAMINSIDEMOVING1')
beamInsideMoving2 = SurfaceFromNodeSet(beamAssembly, beamInstance, 'BEAMINSIDEMOVING2', 'BEAMINSIDEMOVING2')
beamModel.Pressure(name='DistributedPressure0', createStepName='Step-1', distributionType=USER_DEFINED, field='',
                   magnitude=1.0, region=beamInsideMoving0)
beamModel.Pressure(name='DistributedPressure1', createStepName='Step-1', distributionType=USER_DEFINED, field='',
                   magnitude=1.0, region=beamInsideMoving1)
beamModel.Pressure(name='DistributedPressure2', createStepName='Step-1', distributionType=USER_DEFINED, field='',
                   magnitude=1.0, region=beamInsideMoving2)
beamModel.SurfaceTraction(name='DistributedShear0', createStepName='Step-1', region=beamInsideMoving0, magnitude=1,
                          traction=GENERAL, directionVector=((0, 0, 0), (1, 0, 0)), distributionType=USER_DEFINED)
beamModel.SurfaceTraction(name='DistributedShear1', createStepName='Step-1', region=beamInsideMoving1, magnitude=1,
                          traction=GENERAL, directionVector=((0, 0, 0), (1, 0, 0)), distributionType=USER_DEFINED)
beamModel.SurfaceTraction(name='DistributedShear2', createStepName='Step-1', region=beamInsideMoving2, magnitude=1,
                          traction=GENERAL, directionVector=((0, 0, 0), (1, 0, 0)), distributionType=USER_DEFINED)
if gravity > 0.0:
    beamModel.Gravity(name='Gravity', createStepName='Step-1', comp2=-gravity)
beamModel.DisplacementBC(name='FixedTopEnd', createStepName='Step-1', region=beamAssembly.sets['BEAMFIXED'], u1=0, u2=0,
                         ur3=0)
beamModel.FieldOutputRequest(createStepName='Step-1', frequency=LAST_INCREMENT, name='F-Output-1',
                             variables=('COORD', 'U'))
beamModel.FieldOutputRequest(createStepName='Step-1', frequency=LAST_INCREMENT, name='F-Output-2', variables=PRESELECT)
beamModel.HistoryOutputRequest(createStepName='Step-1', frequency=LAST_INCREMENT, name='H-Output-1',
                               variables=PRESELECT)
jobName = 'case_breaking_dam'
beamJob = mdb.Job(name=jobName, model='Model-1', description='breaking_dam')
beamJob.writeInput()
