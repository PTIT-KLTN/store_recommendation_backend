fromflaskimportBlueprint,request,jsonify
fromservices.rabbitmq_serviceimportrabbitmq_service
fromservices.ai_rabbitmq_clientimportget_ai_service_client
fromservices.s3_serviceimportget_s3_service
fromservices.allergy_serviceimportget_allergy_service
fromutils.token_utilsimportdecode_token
importuuid
importlogging

logger=logging.getLogger(__name__)

ai_bp=Blueprint('ai',__name__)


defget_current_user_email():
try:
auth_header=request.headers.get('Authorization')
ifnotauth_header:
returnNone

#Format:"Bearer<token>"
parts=auth_header.split()
iflen(parts)!=2orparts[0].lower()!='bearer':
returnNone

token=parts[1]
user_data=decode_token(token)

ifuser_dataand'email'inuser_data:
returnuser_data['email']

returnNone
exceptException:
returnNone


defapply_allergy_filter(result:dict)->dict:
user_email=get_current_user_email()
cart=result.get('cart')
warnings=list(result.get('warnings',[]))

#Filterallergiesifuserisloggedinandcartexists
ifuser_emailandcartandcart.get('items'):
allergy_service=get_allergy_service()
user_allergies=allergy_service.get_user_allergies(user_email)

ifuser_allergies:
logger.info(f"Filteringallergiesforuser{user_email}:{len(user_allergies)}allergies")

filter_result=allergy_service.filter_cart_items(
cart['items'],
user_allergies
)

#Updatecartwithfiltereditems
cart['items']=filter_result['filtered_items']
cart['total_items']=len(filter_result['filtered_items'])

#Addallergywarnings
warnings.extend(filter_result['allergy_warnings'])

iffilter_result['removed_count']>0:
logger.info(f"Removed{filter_result['removed_count']}allergicingredients")

#Returnupdatedresult
result['cart']=cart
result['warnings']=warnings
returnresult

@ai_bp.route('/text',methods=['POST'])
defprocess_text():
try:
data=request.get_json()
description=data.get('description')

message={
'modelType':'text',
'requestMessage':description
}

response=rabbitmq_service.send_message(message,timeout=25)
returnjsonify(response),200

exceptTimeoutError:
returnjsonify({'message':'Requesttimeout'}),504
exceptExceptionase:
returnjsonify({'message':str(e)}),500

@ai_bp.route('/image',methods=['POST'])
defprocess_image():
try:
if'image'notinrequest.files:
returnjsonify({'message':'Noimagefileprovided'}),400

file=request.files['image']

#TODO:UploadtoS3andgetURL
#Fornow,usingplaceholder
image_url=f"placeholder_{uuid.uuid4()}"

message={
'modelType':'image',
'fileName':image_url
}

response=rabbitmq_service.send_message(message,timeout=15)
returnjsonify(response),200

exceptTimeoutError:
returnjsonify({'message':'Requesttimeout'}),504
exceptExceptionase:
returnjsonify({'message':str(e)}),500


@ai_bp.route('/recipe-analysis',methods=['POST'])
defanalyze_recipe():
"""
AnalyzerecipeusingAIServiceviaRabbitMQ.

Requestbody:
{
"user_input":"Tôimuốnănphởbò"
}

Response(Standardized-10fixedfields):
{
"status":"success|error|guardrail_blocked",
"error":"string|null",
"error_type":"string|null",
"dish":{"name":"...","prep_time":"...","servings":...},
"cart":{"total_items":...,"items":[...]}|null,
"suggestions":[...],
"similar_dishes":[...],
"warnings":[...],
"insights":[...],
"guardrail":{...}|null
}
"""
try:
data=request.get_json()

ifnotdata:
returnjsonify({
'success':False,
'error':'Requestbodyisrequired'
}),400

user_input=data.get('user_input')

ifnotuser_input:
returnjsonify({
'success':False,
'error':'user_inputisrequired'
}),400

ifnotisinstance(user_input,str):
returnjsonify({
'success':False,
'error':'user_inputmustbeastring'
}),400

user_input=user_input.strip()
ifnotuser_input:
returnjsonify({
'success':False,
'error':'user_inputcannotbeempty'
}),400

logger.info(f"🍲Recipeanalysisrequest:{user_input[:100]}...")

#GetAIServiceclient
client=get_ai_service_client()

#Checkconnection
ifnotclient.is_connected():
logger.warning("⚠️AIServiceclientnotconnected,attemptingreconnect...")
try:
client.reconnect()
exceptExceptionasreconnect_error:
logger.error(f"❌Failedtoreconnect:{reconnect_error}")
returnjsonify({
'success':False,
'error':'AIServiceiscurrentlyunavailable.Pleasetryagainlater.'
}),503

#SendrequesttoAIService
response=client.analyze_recipe(user_input)

#AIServicecóthểtrảvề2formats:
#Formatmới(flat):{"status":"...","error":"...","dish":{...},...}
#Formatcũ(nested):{"success":false,"result":{"status":"...",...}}

#Detectformatvànormalize
if'result'inresponseandisinstance(response['result'],dict):
#Formatcũ-extracttừresult
result=response['result']
status=result.get('status','')
else:
#Formatmới-đãflat
result=response
status=response.get('status','')

#Nếuvẫnkhôngcóstatus,fallbackchecksuccessfield(legacy)
ifnotstatusandresponse.get('success')isFalse:
#Legacyformatdetection
if'guardrail'inresultandresult.get('guardrail',{}).get('triggered'):
status='guardrail_blocked'
else:
status='error'

#============================================================
#CASE1:GuardrailBlocked(khônglogerror)
#============================================================
ifstatus=='guardrail_blocked':
logger.info(f"🛡️Guardrailblocked:{user_input[:50]}...")

#Buildresponsevới10fieldschuẩn
returnjsonify({
'status':'guardrail_blocked',
'error':result.get('error','Nộidungviphạmchínhsáchantoàn'),
'error_type':'guardrail_violation',
'message':'Yêucầukhôngphùhợphoặcviphạmchínhsáchantoàn.Vuilòngthửlạivớinộidungkhác.',
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),400

#============================================================
#CASE2:TechnicalErrors(logerrorvàodatabase)
#============================================================
elifstatus=='error':
error_message=result.get('error','UnknownerrorfromAIService')
error_type=result.get('error_type','unknown')
dish_name=result.get('dish',{}).get('name','')

#Auto-detecterror_typenếuchưacó
iferror_type=='unknown':
error_lower=error_message.lower()
if'khôngtìmthấytênmón'inerror_loweror'dishnotfound'inerror_lower:
error_type='dish_not_found'
elif'khôngtìmthấycôngthức'inerror_loweror'recipenotfound'inerror_lower:
error_type='recipe_not_found'
elif'khôngcónguyênliệu'inerror_loweror'novalidingredients'inerror_lower:
error_type='no_valid_ingredients'
elif'tríchxuất'inerror_loweror'extraction'inerror_lower:
error_type='extraction_failed'

#Logerrorvớierror_typeđểphântích
logger.error(f"❌AIServiceerror[{error_type}]:{error_message}")

#Xácđịnhuser-friendlymessagetheoerror_type
iferror_type=='dish_not_found':
user_message='Khôngnhậndiệnđượctênmónăntrongyêucầu.Vuilòngnhậprõhơn(vídụ:"Tôimuốnănphởbò").'
status_code=400
eliferror_type=='recipe_not_found':
user_message=f'Hiệntạichưacócôngthứcchomón"{dish_name}".Vuilòngthửmónkhác.'
status_code=404
eliferror_type=='no_valid_ingredients':
user_message='Khôngthểphântíchdanhsáchnguyênliệu.Vuilòngthửlạihoặcchọnmónkhác.'
status_code=400
eliferror_type=='extraction_failed':
user_message='Lỗihệthốngkhixửlýyêucầu.Vuilòngthửlạisau.'
status_code=500
else:
#Unknownerrortype
user_message=f'Cólỗixảyrakhixửlýyêucầu:{error_message}'
status_code=500

#Buildresponsevới10fieldschuẩn
returnjsonify({
'status':'error',
'error':error_message,
'error_type':error_type,
'message':user_message,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),status_code

#============================================================
#CASE3:Success(loginfo+filterallergies)
#============================================================
elifstatus=='success':
dish_name=result.get('dish',{}).get('name','Unknown')
cart=result.get('cart')
cart_items_count=cart.get('total_items',0)ifcartelse0

logger.info(f"✅Recipeanalysissuccessful:{dish_name}({cart_items_count}items)")

#Applyallergyfiltering(ifuserisloggedin)
result=apply_allergy_filter(result)

#Buildresponsevới10fieldschuẩn
returnjsonify({
'status':'success',
'error':None,
'error_type':None,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),200

#============================================================
#CASE4:Unexpectedstatusvalue
#============================================================
else:
logger.error(f"❌Unexpectedstatus'{status}'fromAIService.Fullresponse:{response}")
returnjsonify({
'status':'error',
'error':'InvalidresponsestatusfromAIService',
'error_type':'invalid_response',
'message':'ĐịnhdạngphảnhồitừAIServicekhônghợplệ.Vuilòngthửlại.',
'dish':{'name':''},
'cart':None,
'suggestions':[],
'similar_dishes':[],
'warnings':[],
'insights':[],
'guardrail':None
}),500

exceptTimeoutErrorase:
logger.error(f"⏱️AIServicetimeout:{e}")
returnjsonify({
'success':False,
'error':'AIServicerequesttimeout.Theserviceistakingtoolongtorespond.Pleasetryagain.'
}),504

exceptExceptionase:
logger.error(f"❌ErrorcallingAIService:{e}",exc_info=True)
returnjsonify({
'success':False,
'error':f'Internalservererror:{str(e)}'
}),500


@ai_bp.route('/recipe-analysis/health',methods=['GET'])
defhealth_check_ai_service():
"""
CheckifAIServiceisresponsive.

Response:
{
"status":"healthy"|"degraded"|"unhealthy",
"ai_service":"connected"|"slow_response"|"disconnected",
"connection":true/false,
"error":"..."(ifunhealthy)
}
"""
try:
client=get_ai_service_client()

#Checkconnectionstatus
is_connected=client.is_connected()

ifnotis_connected:
returnjsonify({
'status':'unhealthy',
'ai_service':'disconnected',
'connection':False
}),503

#Sendsimpletestrequestwithshorttimeout
try:
test_response=client.analyze_recipe("testhealthcheck")

returnjsonify({
'status':'healthy',
'ai_service':'connected',
'connection':True
}),200

exceptTimeoutError:
returnjsonify({
'status':'degraded',
'ai_service':'slow_response',
'connection':True
}),200

exceptExceptionase:
logger.error(f"❌Healthcheckfailed:{e}")
returnjsonify({
'status':'unhealthy',
'ai_service':'error',
'connection':False,
'error':str(e)
}),503


@ai_bp.route('/image-analysis',methods=['POST'])
defanalyze_image():
"""
AnalyzerecipefromimageusingAIServiceviaRabbitMQ.

Requestbody:
{
"s3_url":"eslmzivufwukz7hlsxqq.webp",//S3keyorfullURL
"description":"MónănViệtNam"//Optional
}

Response(Sameformatastextanalysis-10fixedfields):
{
"status":"success|error|guardrail_blocked",
"error":"string|null",
"error_type":"string|null",
"dish":{"name":"...","prep_time":"...","servings":...},
"cart":{"total_items":...,"items":[...]}|null,
"suggestions":[...],
"similar_dishes":[...],
"warnings":[...],
"insights":[...],
"guardrail":{...}|null
}
"""
try:
data=request.get_json()

ifnotdata:
returnjsonify({
'success':False,
'error':'Requestbodyisrequired'
}),400

s3_url=data.get('s3_url')

ifnots3_url:
returnjsonify({
'success':False,
'error':'s3_urlisrequired'
}),400

ifnotisinstance(s3_url,str):
returnjsonify({
'success':False,
'error':'s3_urlmustbeastring'
}),400

s3_url=s3_url.strip()
ifnots3_url:
returnjsonify({
'success':False,
'error':'s3_urlcannotbeempty'
}),400

#Optionaldescription
description=data.get('description','')
ifdescriptionandnotisinstance(description,str):
returnjsonify({
'success':False,
'error':'descriptionmustbeastring'
}),400

logger.info(f"🖼️Imageanalysisrequest:{s3_url}")
ifdescription:
logger.info(f"📝Withdescription:{description[:100]}...")

#GetAIServiceclient
client=get_ai_service_client()

#Checkconnection
ifnotclient.is_connected():
logger.warning("⚠️AIServiceclientnotconnected,attemptingreconnect...")
try:
client.reconnect()
exceptExceptionasreconnect_error:
logger.error(f"❌Failedtoreconnect:{reconnect_error}")
returnjsonify({
'success':False,
'error':'AIServiceiscurrentlyunavailable.Pleasetryagainlater.'
}),503

#SendimageanalysisrequesttoAIService
response=client.analyze_image(s3_url,description)

#Normalizeresponseformat(sameastextanalysis)
if'result'inresponseandisinstance(response['result'],dict):
result=response['result']
status=result.get('status','')
else:
result=response
status=response.get('status','')

ifnotstatusandresponse.get('success')isFalse:
if'guardrail'inresultandresult.get('guardrail',{}).get('triggered'):
status='guardrail_blocked'
else:
status='error'

#============================================================
#CASE1:GuardrailBlocked
#============================================================
ifstatus=='guardrail_blocked':
logger.info(f"🛡️Guardrailblockedimage:{s3_url}")

returnjsonify({
'status':'guardrail_blocked',
'error':result.get('error','Hìnhảnhviphạmchínhsáchantoàn'),
'error_type':'guardrail_violation',
'message':'Hìnhảnhkhôngphùhợphoặcviphạmchínhsáchantoàn.Vuilòngthửlạivớihìnhảnhkhác.',
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),400

#============================================================
#CASE2:TechnicalErrors
#============================================================
elifstatus=='error':
error_message=result.get('error','UnknownerrorfromAIService')
error_type=result.get('error_type','unknown')
dish_name=result.get('dish',{}).get('name','')

#Auto-detecterror_typeforimage-specificerrors
iferror_type=='unknown':
error_lower=error_message.lower()
if's3'inerror_loweror'download'inerror_loweror'image'inerror_lower:
error_type='image_download_failed'
elif'khôngtìmthấytênmón'inerror_loweror'dishnotfound'inerror_lower:
error_type='dish_not_found'
elif'khôngtìmthấycôngthức'inerror_loweror'recipenotfound'inerror_lower:
error_type='recipe_not_found'
elif'khôngcónguyênliệu'inerror_loweror'novalidingredients'inerror_lower:
error_type='no_valid_ingredients'
elif'tríchxuất'inerror_loweror'extraction'inerror_lower:
error_type='extraction_failed'

logger.error(f"❌AIServiceerror[{error_type}]:{error_message}")

#User-friendlymessages
iferror_type=='image_download_failed':
user_message='KhôngthểtảihìnhảnhtừS3.VuilòngkiểmtralạiURLhoặcquyềntruycập.'
status_code=400
eliferror_type=='dish_not_found':
user_message='Khôngnhậndiệnđượcmónăntronghìnhảnh.Vuilòngthửhìnhảnhrõhơnhoặcthêmmôtả.'
status_code=400
eliferror_type=='recipe_not_found':
user_message=f'Hiệntạichưacócôngthứcchomón"{dish_name}".Vuilòngthửmónkhác.'
status_code=404
eliferror_type=='no_valid_ingredients':
user_message='Khôngthểphântíchdanhsáchnguyênliệutừhìnhảnh.Vuilòngthửlại.'
status_code=400
eliferror_type=='extraction_failed':
user_message='Lỗihệthốngkhixửlýhìnhảnh.Vuilòngthửlạisau.'
status_code=500
else:
user_message=f'Cólỗixảyrakhixửlýhìnhảnh:{error_message}'
status_code=500

returnjsonify({
'status':'error',
'error':error_message,
'error_type':error_type,
'message':user_message,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),status_code

#============================================================
#CASE3:Success
#============================================================
elifstatus=='success':
dish_name=result.get('dish',{}).get('name','Unknown')
cart_items=result.get('cart',{}).get('total_items',0)ifresult.get('cart')else0

logger.info(f"✅Imageanalysissuccessful:{dish_name}({cart_items}items)")

returnjsonify({
'status':'success',
'error':None,
'error_type':None,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),200

#============================================================
#CASE4:Unexpectedstatus
#============================================================
else:
logger.error(f"❌Unexpectedstatus'{status}'fromAIService.Fullresponse:{response}")
returnjsonify({
'status':'error',
'error':'InvalidresponsestatusfromAIService',
'error_type':'invalid_response',
'message':'ĐịnhdạngphảnhồitừAIServicekhônghợplệ.Vuilòngthửlại.',
'dish':{'name':''},
'cart':None,
'suggestions':[],
'similar_dishes':[],
'warnings':[],
'insights':[],
'guardrail':None
}),500

exceptTimeoutErrorase:
logger.error(f"⏱️AIServicetimeout:{e}")
returnjsonify({
'success':False,
'error':'AIServicerequesttimeout.Imageprocessingistakingtoolong.Pleasetryagain.'
}),504

exceptExceptionase:
logger.error(f"❌ErrorcallingAIServiceforimage:{e}",exc_info=True)
returnjsonify({
'success':False,
'error':f'Internalservererror:{str(e)}'
}),500


@ai_bp.route('/upload-and-analyze',methods=['POST'])
defupload_and_analyze():
"""
UploadimagetoS3andanalyzerecipeinonerequest.

Thisisaconvenienceendpointthatcombinesuploadandanalysis.

Request(multipart/form-data):
-image:Imagefile(required)
-description:Textdescription(optional)

Response:Sameas/image-analysisendpoint
"""
try:
#Validateimagefile
if'image'notinrequest.files:
returnjsonify({
'success':False,
'error':'Imagefileisrequired'
}),400

file=request.files['image']

iffile.filename=='':
returnjsonify({
'success':False,
'error':'Nofileselected'
}),400

#Validatefileextension
allowed_extensions={'jpg','jpeg','png','webp','gif','bmp','tiff','tif'}
file_ext=file.filename.rsplit('.',1)[-1].lower()if'.'infile.filenameelse''

iffile_extnotinallowed_extensions:
returnjsonify({
'success':False,
'error':f'Invalidfiletype.Allowed:{",".join(allowed_extensions)}'
}),400

#Validatefilesize(max10MB)
file.seek(0,2)#Seektoend
file_size=file.tell()
file.seek(0)#Resettobeginning

max_size=10*1024*1024#10MB
iffile_size>max_size:
returnjsonify({
'success':False,
'error':f'Filetoolarge.Maximumsize:{max_size/(1024*1024)}MB'
}),400

#Getoptionaldescription
description=request.form.get('description','')

logger.info(f"📤Uploadingimage:{file.filename}({file_size/1024:.2f}KB)")

#UploadtoS3
try:
s3_service=get_s3_service()
s3_key=s3_service.upload_image(
file=file,
filename=file.filename,
content_type=file.content_type
)
logger.info(f"✅Imageuploadedsuccessfully:{s3_key}")
exceptExceptionasupload_error:
logger.error(f"❌Failedtouploadimage:{upload_error}")
returnjsonify({
'success':False,
'error':f'Failedtouploadimage:{str(upload_error)}'
}),500

#AnalyzeimageusingAIService
logger.info(f"🔍Analyzinguploadedimage:{s3_key}")

client=get_ai_service_client()

ifnotclient.is_connected():
logger.warning("⚠️AIServiceclientnotconnected,attemptingreconnect...")
try:
client.reconnect()
exceptExceptionasreconnect_error:
logger.error(f"❌Failedtoreconnect:{reconnect_error}")
#Deleteuploadedimageonfailure
s3_service.delete_image(s3_key)
returnjsonify({
'success':False,
'error':'AIServiceiscurrentlyunavailable.Pleasetryagainlater.'
}),503

#Sendanalysisrequest
response=client.analyze_image(s3_key,description)

#Normalizeresponseformat
if'result'inresponseandisinstance(response['result'],dict):
result=response['result']
status=result.get('status','')
else:
result=response
status=response.get('status','')

ifnotstatusandresponse.get('success')isFalse:
if'guardrail'inresultandresult.get('guardrail',{}).get('triggered'):
status='guardrail_blocked'
else:
status='error'

#Buildresponsebasedonstatus
ifstatus=='guardrail_blocked':
logger.info(f"🛡️Guardrailblockeduploadedimage:{s3_key}")
#Deleteinappropriateimage
s3_service.delete_image(s3_key)

returnjsonify({
'status':'guardrail_blocked',
'error':result.get('error','Hìnhảnhviphạmchínhsáchantoàn'),
'error_type':'guardrail_violation',
'message':'Hìnhảnhkhôngphùhợphoặcviphạmchínhsáchantoàn.Vuilòngthửlạivớihìnhảnhkhác.',
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail'),
's3_key':None#Don'treturnkeyforblockedimages
}),400

elifstatus=='error':
error_message=result.get('error','UnknownerrorfromAIService')
error_type=result.get('error_type','unknown')
dish_name=result.get('dish',{}).get('name','')

logger.error(f"❌AIServiceerror[{error_type}]:{error_message}")

#Determineusermessage
iferror_type=='dish_not_found':
user_message='Khôngnhậndiệnđượcmónăntronghìnhảnh.Vuilòngthửhìnhảnhrõhơnhoặcthêmmôtả.'
status_code=400
eliferror_type=='recipe_not_found':
user_message=f'Hiệntạichưacócôngthứcchomón"{dish_name}".Vuilòngthửmónkhác.'
status_code=404
else:
user_message=f'Cólỗixảyrakhixửlýhìnhảnh:{error_message}'
status_code=500

returnjsonify({
'status':'error',
'error':error_message,
'error_type':error_type,
'message':user_message,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail'),
's3_key':s3_key#Returnkeyevenonerrorfordebugging
}),status_code

elifstatus=='success':
dish_name=result.get('dish',{}).get('name','Unknown')
cart_items=result.get('cart',{}).get('total_items',0)ifresult.get('cart')else0

logger.info(f"✅Uploadandanalysissuccessful:{dish_name}({cart_items}items)")

returnjsonify({
'status':'success',
'error':None,
'error_type':None,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail'),
's3_key':s3_key#ReturnS3keyforfuturereference
}),200

else:
logger.error(f"❌Unexpectedstatus'{status}'fromAIService")
returnjsonify({
'status':'error',
'error':'InvalidresponsestatusfromAIService',
'error_type':'invalid_response',
'message':'ĐịnhdạngphảnhồitừAIServicekhônghợplệ.Vuilòngthửlại.',
'dish':{'name':''},
'cart':None,
'suggestions':[],
'similar_dishes':[],
'warnings':[],
'insights':[],
'guardrail':None,
's3_key':s3_key
}),500

exceptTimeoutErrorase:
logger.error(f"⏱️AIServicetimeout:{e}")
returnjsonify({
'success':False,
'error':'AIServicerequesttimeout.Imageprocessingistakingtoolong.Pleasetryagain.'
}),504

exceptExceptionase:
logger.error(f"❌Errorinuploadandanalyze:{e}",exc_info=True)
returnjsonify({
'success':False,
'error':f'Internalservererror:{str(e)}'
}),500
defanalyze_image():
"""
AnalyzerecipefromimageusingAIServiceviaRabbitMQ.

Requestbody:
{
"s3_url":"eslmzivufwukz7hlsxqq.webp",//S3keyorfullURL
"description":"MónănViệtNam"//Optional
}

Response(Sameformatastextanalysis-10fixedfields):
{
"status":"success|error|guardrail_blocked",
"error":"string|null",
"error_type":"string|null",
"dish":{"name":"...","prep_time":"...","servings":...},
"cart":{"total_items":...,"items":[...]}|null,
"suggestions":[...],
"similar_dishes":[...],
"warnings":[...],
"insights":[...],
"guardrail":{...}|null
}
"""
try:
data=request.get_json()

ifnotdata:
returnjsonify({
'success':False,
'error':'Requestbodyisrequired'
}),400

s3_url=data.get('s3_url')

ifnots3_url:
returnjsonify({
'success':False,
'error':'s3_urlisrequired'
}),400

ifnotisinstance(s3_url,str):
returnjsonify({
'success':False,
'error':'s3_urlmustbeastring'
}),400

s3_url=s3_url.strip()
ifnots3_url:
returnjsonify({
'success':False,
'error':'s3_urlcannotbeempty'
}),400

#Optionaldescription
description=data.get('description','')
ifdescriptionandnotisinstance(description,str):
returnjsonify({
'success':False,
'error':'descriptionmustbeastring'
}),400

logger.info(f"🖼️Imageanalysisrequest:{s3_url}")
ifdescription:
logger.info(f"📝Withdescription:{description[:100]}...")

#GetAIServiceclient
client=get_ai_service_client()

#Checkconnection
ifnotclient.is_connected():
logger.warning("⚠️AIServiceclientnotconnected,attemptingreconnect...")
try:
client.reconnect()
exceptExceptionasreconnect_error:
logger.error(f"❌Failedtoreconnect:{reconnect_error}")
returnjsonify({
'success':False,
'error':'AIServiceiscurrentlyunavailable.Pleasetryagainlater.'
}),503

#SendimageanalysisrequesttoAIService
response=client.analyze_image(s3_url,description)

#Normalizeresponseformat(sameastextanalysis)
if'result'inresponseandisinstance(response['result'],dict):
result=response['result']
status=result.get('status','')
else:
result=response
status=response.get('status','')

ifnotstatusandresponse.get('success')isFalse:
if'guardrail'inresultandresult.get('guardrail',{}).get('triggered'):
status='guardrail_blocked'
else:
status='error'

#============================================================
#CASE1:GuardrailBlocked
#============================================================
ifstatus=='guardrail_blocked':
logger.info(f"🛡️Guardrailblockedimage:{s3_url}")

returnjsonify({
'status':'guardrail_blocked',
'error':result.get('error','Hìnhảnhviphạmchínhsáchantoàn'),
'error_type':'guardrail_violation',
'message':'Hìnhảnhkhôngphùhợphoặcviphạmchínhsáchantoàn.Vuilòngthửlạivớihìnhảnhkhác.',
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),400

#============================================================
#CASE2:TechnicalErrors
#============================================================
elifstatus=='error':
error_message=result.get('error','UnknownerrorfromAIService')
error_type=result.get('error_type','unknown')
dish_name=result.get('dish',{}).get('name','')

#Auto-detecterror_typeforimage-specificerrors
iferror_type=='unknown':
error_lower=error_message.lower()
if's3'inerror_loweror'download'inerror_loweror'image'inerror_lower:
error_type='image_download_failed'
elif'khôngtìmthấytênmón'inerror_loweror'dishnotfound'inerror_lower:
error_type='dish_not_found'
elif'khôngtìmthấycôngthức'inerror_loweror'recipenotfound'inerror_lower:
error_type='recipe_not_found'
elif'khôngcónguyênliệu'inerror_loweror'novalidingredients'inerror_lower:
error_type='no_valid_ingredients'
elif'tríchxuất'inerror_loweror'extraction'inerror_lower:
error_type='extraction_failed'

logger.error(f"❌AIServiceerror[{error_type}]:{error_message}")

#User-friendlymessages
iferror_type=='image_download_failed':
user_message='KhôngthểtảihìnhảnhtừS3.VuilòngkiểmtralạiURLhoặcquyềntruycập.'
status_code=400
eliferror_type=='dish_not_found':
user_message='Khôngnhậndiệnđượcmónăntronghìnhảnh.Vuilòngthửhìnhảnhrõhơnhoặcthêmmôtả.'
status_code=400
eliferror_type=='recipe_not_found':
user_message=f'Hiệntạichưacócôngthứcchomón"{dish_name}".Vuilòngthửmónkhác.'
status_code=404
eliferror_type=='no_valid_ingredients':
user_message='Khôngthểphântíchdanhsáchnguyênliệutừhìnhảnh.Vuilòngthửlại.'
status_code=400
eliferror_type=='extraction_failed':
user_message='Lỗihệthốngkhixửlýhìnhảnh.Vuilòngthửlạisau.'
status_code=500
else:
user_message=f'Cólỗixảyrakhixửlýhìnhảnh:{error_message}'
status_code=500

returnjsonify({
'status':'error',
'error':error_message,
'error_type':error_type,
'message':user_message,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),status_code

#============================================================
#CASE3:Success
#============================================================
elifstatus=='success':
dish_name=result.get('dish',{}).get('name','Unknown')
cart_items=result.get('cart',{}).get('total_items',0)ifresult.get('cart')else0

logger.info(f"✅Imageanalysissuccessful:{dish_name}({cart_items}items)")

returnjsonify({
'status':'success',
'error':None,
'error_type':None,
'dish':result.get('dish',{'name':''}),
'cart':result.get('cart'),
'suggestions':result.get('suggestions',[]),
'similar_dishes':result.get('similar_dishes',[]),
'warnings':result.get('warnings',[]),
'insights':result.get('insights',[]),
'guardrail':result.get('guardrail')
}),200

#============================================================
#CASE4:Unexpectedstatus
#============================================================
else:
logger.error(f"❌Unexpectedstatus'{status}'fromAIService.Fullresponse:{response}")
returnjsonify({
'status':'error',
'error':'InvalidresponsestatusfromAIService',
'error_type':'invalid_response',
'message':'ĐịnhdạngphảnhồitừAIServicekhônghợplệ.Vuilòngthửlại.',
'dish':{'name':''},
'cart':None,
'suggestions':[],
'similar_dishes':[],
'warnings':[],
'insights':[],
'guardrail':None
}),500

exceptTimeoutErrorase:
logger.error(f"⏱️AIServicetimeout:{e}")
returnjsonify({
'success':False,
'error':'AIServicerequesttimeout.Imageprocessingistakingtoolong.Pleasetryagain.'
}),504

exceptExceptionase:
logger.error(f"❌ErrorcallingAIServiceforimage:{e}",exc_info=True)
returnjsonify({
'success':False,
'error':f'Internalservererror:{str(e)}'
}),500
