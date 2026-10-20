// Codex artifact validation helper; run using bundled Node and RUNTIME_NODE_MODULES.
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/,'$1')),'..');
const skill=path.join(process.env.USERPROFILE,'.codex/plugins/cache/openai-primary-runtime/presentations/26.1015.12040/skills/presentations');
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const tables=[3,6,9,14,17,19],charts=[7,8,10,11,12,13,15,18];
const stamp=Date.now().toString();
const result=await finalizePresentation({workspaceDir:root,candidatePath:path.join(root,'tmp/candidate-v4-submission.pptx'),
 finalPath:path.join(root,'output/builds/SELF_X_Presentation_'+stamp+'.pptx'),
 pythonExecutable:path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...tables.flatMap(n=>['--require-native-table-slide',String(n)])],
 explicitTotalSlideCount:20,requiredNativeTableOwnerSlides:tables,requiredNativeChartOwnerSlides:charts,
 materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,
 receiptPath:path.join(root,'tmp/presentation_validation_'+stamp+'.json')});
console.log(JSON.stringify({path:result.finalPath,bytes:result.byteCount,integrity:result.packageIntegrity.status,charts:result.nativeChartValidation.passed}));
