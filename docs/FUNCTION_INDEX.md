# Índice de funções, classes e rotas

Atualizado em **20/10/2026** após a reestruturação offline. Gere novamente com
`python scripts/update_function_index.py`. Complementa [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

São 483 declarações Python/JavaScript indexadas e 39 rotas HTTP explícitas.
Python usa AST; JavaScript usa declarações `function` nomeadas, inclusive no HTML.
Não enumera callbacks anônimos, funções arrow, métodos Java nem constitui grafo de chamadas.
A entrada nativa é `mobile/android/app/src/main/java/br/com/siopa/offline/MainActivity.java`.

## Rotas HTTP

Os caminhos abaixo já incluem `/api/v1` nos roteadores da API.

| Método e caminho | Arquivo e linha |
| --- | --- |
| `POST /api/v1/dataset/upload` | [app/api/dataset_routes.py:36](../app/api/dataset_routes.py#L36) |
| `GET /api/v1/dataset/images` | [app/api/dataset_routes.py:108](../app/api/dataset_routes.py#L108) |
| `GET /api/v1/ml/training/{session_id}/status` | [app/api/dataset_routes.py:161](../app/api/dataset_routes.py#L161) |
| `POST /api/v1/ml/train` | [app/api/dataset_routes.py:169](../app/api/dataset_routes.py#L169) |
| `GET /api/v1/dataset/image/{image_id}` | [app/api/dataset_routes.py:225](../app/api/dataset_routes.py#L225) |
| `POST /api/v1/dataset/image/{image_id}/annotations` | [app/api/dataset_routes.py:253](../app/api/dataset_routes.py#L253) |
| `GET /api/v1/dataset/image/{image_id}/annotations` | [app/api/dataset_routes.py:363](../app/api/dataset_routes.py#L363) |
| `PUT /api/v1/dataset/annotation/{annotation_id}/review` | [app/api/dataset_routes.py:405](../app/api/dataset_routes.py#L405) |
| `GET /api/v1/models` | [app/api/dataset_routes.py:456](../app/api/dataset_routes.py#L456) |
| `POST /api/v1/models` | [app/api/dataset_routes.py:488](../app/api/dataset_routes.py#L488) |
| `POST /api/v1/training/start` | [app/api/dataset_routes.py:529](../app/api/dataset_routes.py#L529) |
| `GET /api/v1/training/sessions` | [app/api/dataset_routes.py:596](../app/api/dataset_routes.py#L596) |
| `GET /api/v1/dataset/stats` | [app/api/dataset_routes.py:631](../app/api/dataset_routes.py#L631) |
| `GET /api/v1/dataset/export` | [app/api/dataset_routes.py:676](../app/api/dataset_routes.py#L676) |
| `GET /api/v1/health` | [app/api/routes_new.py:107](../app/api/routes_new.py#L107) |
| `GET /api/v1/client/config` | [app/api/routes_new.py:113](../app/api/routes_new.py#L113) |
| `GET /api/v1/offline/bootstrap` | [app/api/routes_new.py:125](../app/api/routes_new.py#L125) |
| `GET /api/v1/environment/{latitude}/{longitude}` | [app/api/routes_new.py:148](../app/api/routes_new.py#L148) |
| `GET /api/v1/crops` | [app/api/routes_new.py:157](../app/api/routes_new.py#L157) |
| `POST /api/v1/analyze-image` | [app/api/routes_new.py:162](../app/api/routes_new.py#L162) |
| `POST /api/v1/test-analysis` | [app/api/routes_new.py:210](../app/api/routes_new.py#L210) |
| `GET /api/v1/weather/{latitude}/{longitude}` | [app/api/routes_new.py:216](../app/api/routes_new.py#L216) |
| `GET /api/v1/weather/forecast/{latitude}/{longitude}` | [app/api/routes_new.py:225](../app/api/routes_new.py#L225) |
| `GET /api/v1/agriculture/{crop_type}` | [app/api/routes_new.py:234](../app/api/routes_new.py#L234) |
| `GET /api/v1/crop/{crop_type}` | [app/api/routes_new.py:251](../app/api/routes_new.py#L251) |
| `GET /api/v1/soil/{latitude}/{longitude}` | [app/api/routes_new.py:257](../app/api/routes_new.py#L257) |
| `GET /api/v1/agrofit/products` | [app/api/routes_new.py:266](../app/api/routes_new.py#L266) |
| `POST /api/v1/agrofit/sync` | [app/api/routes_new.py:278](../app/api/routes_new.py#L278) |
| `GET /api/v1/recommendations/preview` | [app/api/routes_new.py:286](../app/api/routes_new.py#L286) |
| `GET /api/v1/system/stats` | [app/api/routes_new.py:309](../app/api/routes_new.py#L309) |
| `GET /api/v1/system/runtime` | [app/api/routes_new.py:319](../app/api/routes_new.py#L319) |
| `GET /api/v1/statistics` | [app/api/routes_new.py:324](../app/api/routes_new.py#L324) |
| `GET /favicon.ico` | [main.py:98](../main.py#L98) |
| `GET /service-worker.js` | [main.py:102](../main.py#L102) |
| `GET /manifest.webmanifest` | [main.py:110](../main.py#L110) |
| `GET /icon.svg` | [main.py:114](../main.py#L114) |
| `GET /` | [main.py:118](../main.py#L118) |
| `GET /health` | [main.py:130](../main.py#L130) |
| `GET /health/readiness` | [main.py:145](../main.py#L145) |

## Declarações por arquivo

### app/api/dataset_routes.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `upload_dataset_image` | async def | [37](../app/api/dataset_routes.py#L37) |
| `list_dataset_images` | async def | [109](../app/api/dataset_routes.py#L109) |
| `api_ml_training_status` | async def | [162](../app/api/dataset_routes.py#L162) |
| `api_ml_train` | async def | [170](../app/api/dataset_routes.py#L170) |
| `get_dataset_image` | async def | [226](../app/api/dataset_routes.py#L226) |
| `create_annotations` | async def | [254](../app/api/dataset_routes.py#L254) |
| `get_annotations` | async def | [364](../app/api/dataset_routes.py#L364) |
| `review_annotation` | async def | [406](../app/api/dataset_routes.py#L406) |
| `list_ml_models` | async def | [457](../app/api/dataset_routes.py#L457) |
| `create_ml_model` | async def | [489](../app/api/dataset_routes.py#L489) |
| `start_training_session` | async def | [530](../app/api/dataset_routes.py#L530) |
| `list_training_sessions` | async def | [597](../app/api/dataset_routes.py#L597) |
| `get_dataset_statistics` | async def | [632](../app/api/dataset_routes.py#L632) |
| `export_dataset` | async def | [677](../app/api/dataset_routes.py#L677) |

### app/api/routes_new.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_validate_coordinates` | def | [38](../app/api/routes_new.py#L38) |
| `_verify_image` | def | [49](../app/api/routes_new.py#L49) |
| `_save_temp_upload` | async def | [65](../app/api/routes_new.py#L65) |
| `_profile` | def | [76](../app/api/routes_new.py#L76) |
| `_no_environment` | def | [100](../app/api/routes_new.py#L100) |
| `health_check` | async def | [108](../app/api/routes_new.py#L108) |
| `get_client_config` | async def | [114](../app/api/routes_new.py#L114) |
| `offline_bootstrap` | async def | [126](../app/api/routes_new.py#L126) |
| `get_environment` | async def | [149](../app/api/routes_new.py#L149) |
| `get_crops` | async def | [158](../app/api/routes_new.py#L158) |
| `analyze_image` | async def | [163](../app/api/routes_new.py#L163) |
| `test_analysis` | async def | [211](../app/api/routes_new.py#L211) |
| `get_weather_info` | async def | [217](../app/api/routes_new.py#L217) |
| `get_weather_forecast` | async def | [226](../app/api/routes_new.py#L226) |
| `get_agriculture_info` | async def | [235](../app/api/routes_new.py#L235) |
| `get_crop_info_alias` | async def | [252](../app/api/routes_new.py#L252) |
| `get_soil_info` | async def | [258](../app/api/routes_new.py#L258) |
| `search_agrofit_products` | async def | [267](../app/api/routes_new.py#L267) |
| `sync_agrofit_products` | async def | [279](../app/api/routes_new.py#L279) |
| `preview_recommendations` | async def | [287](../app/api/routes_new.py#L287) |
| `get_system_stats` | async def | [310](../app/api/routes_new.py#L310) |
| `get_runtime_summary` | async def | [320](../app/api/routes_new.py#L320) |
| `get_statistics_alias` | async def | [325](../app/api/routes_new.py#L325) |

### app/core/access.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `require_admin_access` | def | [11](../app/core/access.py#L11) |

### app/core/config.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `Settings` | classe | [13](../app/core/config.py#L13) |
| `Settings.parse_list_fields` | def | [84](../app/core/config.py#L84) |
| `Settings.normalize_root_path` | def | [106](../app/core/config.py#L106) |
| `Settings.normalize_environment` | def | [115](../app/core/config.py#L115) |
| `Settings.normalize_debug_flag` | def | [123](../app/core/config.py#L123) |
| `Settings.normalize_public_base_url` | def | [139](../app/core/config.py#L139) |
| `Settings.create_directories` | def | [156](../app/core/config.py#L156) |
| `Settings.resolved_database_url` | def | [169](../app/core/config.py#L169) |
| `Settings.database_backend` | def | [178](../app/core/config.py#L178) |
| `Settings.sqlite_database_path` | def | [183](../app/core/config.py#L183) |
| `Settings.is_production` | def | [192](../app/core/config.py#L192) |
| `Settings.max_upload_size_mb` | def | [197](../app/core/config.py#L197) |

### app/core/database.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_build_engine` | def | [17](../app/core/database.py#L17) |
| `init_database` | def | [47](../app/core/database.py#L47) |
| `get_db` | def | [68](../app/core/database.py#L68) |
| `_create_initial_data` | def | [79](../app/core/database.py#L79) |
| `_apply_lightweight_migrations` | def | [112](../app/core/database.py#L112) |
| `reset_database` | def | [145](../app/core/database.py#L145) |
| `backup_database` | def | [160](../app/core/database.py#L160) |
| `get_database_stats` | def | [187](../app/core/database.py#L187) |
| `DatabaseTransaction` | classe | [221](../app/core/database.py#L221) |
| `DatabaseTransaction.__init__` | def | [226](../app/core/database.py#L226) |
| `DatabaseTransaction.__enter__` | def | [229](../app/core/database.py#L229) |
| `DatabaseTransaction.__exit__` | def | [233](../app/core/database.py#L233) |
| `with_db_session` | def | [243](../app/core/database.py#L243) |
| `with_db_session.wrapper` | def | [248](../app/core/database.py#L248) |

### app/core/exceptions.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `CustomException` | classe | [14](../app/core/exceptions.py#L14) |
| `CustomException.__init__` | def | [16](../app/core/exceptions.py#L16) |
| `ImageProcessingError` | classe | [22](../app/core/exceptions.py#L22) |
| `ImageProcessingError.__init__` | def | [24](../app/core/exceptions.py#L24) |
| `ModelLoadError` | classe | [27](../app/core/exceptions.py#L27) |
| `ModelLoadError.__init__` | def | [29](../app/core/exceptions.py#L29) |
| `APIConnectionError` | classe | [32](../app/core/exceptions.py#L32) |
| `APIConnectionError.__init__` | def | [34](../app/core/exceptions.py#L34) |
| `ValidationError` | classe | [40](../app/core/exceptions.py#L40) |
| `ValidationError.__init__` | def | [42](../app/core/exceptions.py#L42) |
| `DatabaseError` | classe | [48](../app/core/exceptions.py#L48) |
| `DatabaseError.__init__` | def | [50](../app/core/exceptions.py#L50) |
| `FileProcessingError` | classe | [53](../app/core/exceptions.py#L53) |
| `FileProcessingError.__init__` | def | [55](../app/core/exceptions.py#L55) |
| `custom_exception_handler` | async def | [61](../app/core/exceptions.py#L61) |
| `http_exception_handler` | async def | [79](../app/core/exceptions.py#L79) |
| `validation_exception_handler` | async def | [95](../app/core/exceptions.py#L95) |
| `general_exception_handler` | async def | [120](../app/core/exceptions.py#L120) |
| `setup_exception_handlers` | def | [143](../app/core/exceptions.py#L143) |

### app/core/runtime.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_path_status` | def | [22](../app/core/runtime.py#L22) |
| `build_runtime_report` | def | [31](../app/core/runtime.py#L31) |

### app/models/database.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `ImageDataset` | classe | [15](../app/models/database.py#L15) |
| `ImageAnnotation` | classe | [51](../app/models/database.py#L51) |
| `ApplicationCondition` | classe | [94](../app/models/database.py#L94) |
| `AnalysisResult` | classe | [140](../app/models/database.py#L140) |
| `MLModel` | classe | [180](../app/models/database.py#L180) |
| `TrainingSession` | classe | [225](../app/models/database.py#L225) |
| `DatasetSplit` | classe | [269](../app/models/database.py#L269) |
| `AnnotationTask` | classe | [289](../app/models/database.py#L289) |
| `create_image_entry` | def | [327](../app/models/database.py#L327) |
| `create_annotation` | def | [350](../app/models/database.py#L350) |
| `get_training_ready_images` | def | [373](../app/models/database.py#L373) |
| `get_model_performance_summary` | def | [382](../app/models/database.py#L382) |

### app/models/image_analysis.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_option` | def | [25](../app/models/image_analysis.py#L25) |
| `_positive` | def | [29](../app/models/image_analysis.py#L29) |
| `_polygon_area` | def | [37](../app/models/image_analysis.py#L37) |
| `_canonical_corners` | def | [42](../app/models/image_analysis.py#L42) |
| `DropletAnalyzer` | classe | [58](../app/models/image_analysis.py#L58) |
| `DropletAnalyzer.__init__` | def | [61](../app/models/image_analysis.py#L61) |
| `DropletAnalyzer.load_model` | def | [73](../app/models/image_analysis.py#L73) |
| `DropletAnalyzer._order_points` | def | [78](../app/models/image_analysis.py#L78) |
| `DropletAnalyzer._resize_long_edge` | def | [82](../app/models/image_analysis.py#L82) |
| `DropletAnalyzer._detect_paper_region` | def | [88](../app/models/image_analysis.py#L88) |
| `DropletAnalyzer.preprocess_image` | def | [128](../app/models/image_analysis.py#L128) |
| `DropletAnalyzer.segment_droplets` | def | [189](../app/models/image_analysis.py#L189) |
| `DropletAnalyzer._segment_with_opencv` | def | [192](../app/models/image_analysis.py#L192) |
| `DropletAnalyzer._component_geometry` | def | [205](../app/models/image_analysis.py#L205) |
| `DropletAnalyzer.analyze_droplets` | def | [227](../app/models/image_analysis.py#L227) |
| `DropletAnalyzer._volume_quantile` | def | [335](../app/models/image_analysis.py#L335) |
| `DropletAnalyzer._extract_patch_features` | def | [345](../app/models/image_analysis.py#L345) |
| `DropletAnalyzer._calculate_quality_score` | def | [348](../app/models/image_analysis.py#L348) |
| `DropletAnalyzer._assess_quality` | def | [353](../app/models/image_analysis.py#L353) |
| `DropletAnalyzer._generate_recommendations` | def | [357](../app/models/image_analysis.py#L357) |
| `DropletAnalyzer.process_image` | def | [367](../app/models/image_analysis.py#L367) |

### app/services/agriculture_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `AgricultureService` | classe | [9](../app/services/agriculture_service.py#L9) |
| `AgricultureService.get_supported_crops` | def | [10](../app/services/agriculture_service.py#L10) |
| `AgricultureService._normalize_crop_key` | def | [13](../app/services/agriculture_service.py#L13) |
| `AgricultureService.get_crop_info` | async def | [17](../app/services/agriculture_service.py#L17) |
| `AgricultureService._get_location_context` | async def | [37](../app/services/agriculture_service.py#L37) |
| `AgricultureService.get_soil_info` | async def | [44](../app/services/agriculture_service.py#L44) |

### app/services/agrofit_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `AgrofitResource` | classe | [26](../app/services/agrofit_service.py#L26) |
| `AgrofitService` | classe | [32](../app/services/agrofit_service.py#L32) |
| `AgrofitService.__init__` | def | [35](../app/services/agrofit_service.py#L35) |
| `AgrofitService.sync_products` | def | [42](../app/services/agrofit_service.py#L42) |
| `AgrofitService.load_products` | def | [79](../app/services/agrofit_service.py#L79) |
| `AgrofitService.search_products` | def | [101](../app/services/agrofit_service.py#L101) |
| `AgrofitService._discover_formulated_product_resource` | def | [138](../app/services/agrofit_service.py#L138) |
| `AgrofitService._score_product` | def | [168](../app/services/agrofit_service.py#L168) |
| `AgrofitService._normalize_record` | def | [189](../app/services/agrofit_service.py#L189) |
| `AgrofitService._first_matching` | def | [212](../app/services/agrofit_service.py#L212) |
| `AgrofitService._is_cache_stale` | def | [219](../app/services/agrofit_service.py#L219) |
| `AgrofitService._read_metadata` | def | [225](../app/services/agrofit_service.py#L225) |
| `AgrofitService._decode_csv` | def | [234](../app/services/agrofit_service.py#L234) |
| `AgrofitService._sniff_dialect` | def | [243](../app/services/agrofit_service.py#L243) |
| `AgrofitService._normalize_text` | def | [251](../app/services/agrofit_service.py#L251) |

### app/services/crop_catalog.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `normalize_crop_name` | def | [13](../app/services/crop_catalog.py#L13) |
| `CropCatalog` | classe | [18](../app/services/crop_catalog.py#L18) |
| `CropCatalog.__init__` | def | [19](../app/services/crop_catalog.py#L19) |
| `CropCatalog._load` | def | [24](../app/services/crop_catalog.py#L24) |
| `CropCatalog.list_crops` | def | [40](../app/services/crop_catalog.py#L40) |
| `CropCatalog.get_crop` | def | [43](../app/services/crop_catalog.py#L43) |
| `CropCatalog.quality_profile` | def | [48](../app/services/crop_catalog.py#L48) |
| `CropCatalog.metadata` | def | [55](../app/services/crop_catalog.py#L55) |

### app/services/environmental_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `EnvironmentalService` | classe | [20](../app/services/environmental_service.py#L20) |
| `EnvironmentalService.__init__` | def | [21](../app/services/environmental_service.py#L21) |
| `EnvironmentalService._soil_provenance` | def | [29](../app/services/environmental_service.py#L29) |
| `EnvironmentalService._terrain_provenance` | def | [38](../app/services/environmental_service.py#L38) |
| `EnvironmentalService._request_json` | async def | [46](../app/services/environmental_service.py#L46) |
| `EnvironmentalService._fetch_soil` | async def | [52](../app/services/environmental_service.py#L52) |
| `EnvironmentalService._normalize_soil` | def | [69](../app/services/environmental_service.py#L69) |
| `EnvironmentalService.get_soil` | async def | [101](../app/services/environmental_service.py#L101) |
| `EnvironmentalService._fetch_terrain` | async def | [113](../app/services/environmental_service.py#L113) |
| `EnvironmentalService.get_terrain` | async def | [132](../app/services/environmental_service.py#L132) |
| `EnvironmentalService.get_context` | async def | [142](../app/services/environmental_service.py#L142) |

### app/services/ml_training.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `split_by_source_image` | def | [43](../app/services/ml_training.py#L43) |
| `MLTrainer` | classe | [57](../app/services/ml_training.py#L57) |
| `MLTrainer.__init__` | def | [62](../app/services/ml_training.py#L62) |
| `MLTrainer.start_training_session` | def | [68](../app/services/ml_training.py#L68) |
| `MLTrainer._run_training` | def | [112](../app/services/ml_training.py#L112) |
| `MLTrainer._prepare_training_data` | def | [201](../app/services/ml_training.py#L201) |
| `MLTrainer._extract_annotation_patch` | def | [287](../app/services/ml_training.py#L287) |
| `MLTrainer._annotation_to_label` | def | [306](../app/services/ml_training.py#L306) |
| `MLTrainer._is_near_annotation` | def | [345](../app/services/ml_training.py#L345) |
| `MLTrainer._extract_patch_features` | def | [353](../app/services/ml_training.py#L353) |
| `MLTrainer._train_random_forest` | def | [357](../app/services/ml_training.py#L357) |
| `MLTrainer._train_svm` | def | [401](../app/services/ml_training.py#L401) |
| `MLTrainer._evaluate_model` | def | [436](../app/services/ml_training.py#L436) |
| `MLTrainer._attach_model_metadata` | def | [456](../app/services/ml_training.py#L456) |
| `MLTrainer._save_model` | def | [479](../app/services/ml_training.py#L479) |
| `MLTrainer._update_training_progress` | def | [493](../app/services/ml_training.py#L493) |
| `MLTrainer._update_training_results` | def | [523](../app/services/ml_training.py#L523) |
| `MLTrainer._mark_training_failed` | def | [564](../app/services/ml_training.py#L564) |
| `MLTrainer.get_training_status` | def | [583](../app/services/ml_training.py#L583) |
| `MLTrainer.load_best_model` | def | [610](../app/services/ml_training.py#L610) |
| `start_training` | def | [659](../app/services/ml_training.py#L659) |
| `get_training_progress` | def | [710](../app/services/ml_training.py#L710) |
| `load_active_model` | def | [716](../app/services/ml_training.py#L716) |

### app/services/recommendation_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `PesticideRecommendationService` | classe | [9](../app/services/recommendation_service.py#L9) |
| `PesticideRecommendationService.build_recommendation` | def | [12](../app/services/recommendation_service.py#L12) |
| `PesticideRecommendationService._weather_suitability` | def | [73](../app/services/recommendation_service.py#L73) |
| `PesticideRecommendationService.get_pesticide_recommendation` | async def | [82](../app/services/recommendation_service.py#L82) |

### app/services/spray_quality.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_number` | def | [20](../app/services/spray_quality.py#L20) |
| `_ramp` | def | [30](../app/services/spray_quality.py#L30) |
| `_members` | def | [34](../app/services/spray_quality.py#L34) |
| `evaluate_quality` | def | [42](../app/services/spray_quality.py#L42) |

### app/services/vision_features.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `extract_patch_features` | def | [33](../app/services/vision_features.py#L33) |
| `_foreground_mask` | def | [110](../app/services/vision_features.py#L110) |
| `_center_background_delta` | def | [124](../app/services/vision_features.py#L124) |

### app/services/weather_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `utc_now` | def | [33](../app/services/weather_service.py#L33) |
| `validate_coordinates` | def | [37](../app/services/weather_service.py#L37) |
| `SnapshotCache` | classe | [42](../app/services/weather_service.py#L42) |
| `SnapshotCache.__init__` | def | [49](../app/services/weather_service.py#L49) |
| `SnapshotCache._path` | def | [53](../app/services/weather_service.py#L53) |
| `SnapshotCache.read` | def | [56](../app/services/weather_service.py#L56) |
| `SnapshotCache._write` | def | [71](../app/services/weather_service.py#L71) |
| `SnapshotCache._decorate` | def | [88](../app/services/weather_service.py#L88) |
| `SnapshotCache.resolve` | async def | [97](../app/services/weather_service.py#L97) |
| `WeatherService` | classe | [124](../app/services/weather_service.py#L124) |
| `WeatherService.__init__` | def | [127](../app/services/weather_service.py#L127) |
| `WeatherService.get_current_weather` | async def | [162](../app/services/weather_service.py#L162) |
| `WeatherService._unavailable_current` | def | [174](../app/services/weather_service.py#L174) |
| `WeatherService._unknown_conditions` | def | [183](../app/services/weather_service.py#L183) |
| `WeatherService.get_weather_bundle` | async def | [189](../app/services/weather_service.py#L189) |
| `WeatherService.get_weather_bundle.fetch_bundle` | async def | [195](../app/services/weather_service.py#L195) |
| `WeatherService._get_open_meteo_bundle` | async def | [234](../app/services/weather_service.py#L234) |
| `WeatherService._get_open_meteo_bundle.normalize` | def | [254](../app/services/weather_service.py#L254) |
| `WeatherService._get_open_meteo_bundle.values` | def | [277](../app/services/weather_service.py#L277) |
| `WeatherService._weather_code_text` | def | [291](../app/services/weather_service.py#L291) |
| `WeatherService._number` | def | [305](../app/services/weather_service.py#L305) |
| `WeatherService._observation_time` | def | [313](../app/services/weather_service.py#L313) |
| `WeatherService._get_weather_from_apis` | async def | [319](../app/services/weather_service.py#L319) |
| `WeatherService._request_json` | async def | [355](../app/services/weather_service.py#L355) |
| `WeatherService._get_openweather_data` | async def | [394](../app/services/weather_service.py#L394) |
| `WeatherService._get_weatherapi_data` | async def | [430](../app/services/weather_service.py#L430) |
| `WeatherService._get_agromonitoring_current_weather` | async def | [469](../app/services/weather_service.py#L469) |
| `WeatherService._get_climatempo_data` | async def | [509](../app/services/weather_service.py#L509) |
| `WeatherService._consolidate_weather_data` | def | [547](../app/services/weather_service.py#L547) |
| `WeatherService._analyze_spray_conditions` | def | [602](../app/services/weather_service.py#L602) |
| `WeatherService.get_weather_forecast` | async def | [682](../app/services/weather_service.py#L682) |
| `WeatherService._get_forecast_from_apis` | async def | [692](../app/services/weather_service.py#L692) |
| `WeatherService._get_openweather_forecast` | async def | [726](../app/services/weather_service.py#L726) |
| `WeatherService._get_weatherapi_forecast` | async def | [748](../app/services/weather_service.py#L748) |
| `WeatherService._get_agromonitoring_forecast` | async def | [789](../app/services/weather_service.py#L789) |
| `WeatherService._aggregate_three_hour_forecast` | def | [810](../app/services/weather_service.py#L810) |
| `WeatherService._merge_daily_forecasts` | def | [851](../app/services/weather_service.py#L851) |
| `WeatherService._normalize_temperature` | def | [901](../app/services/weather_service.py#L901) |

### app/static/analysis-engine.js

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `evaluateQuality` | function | [17](../app/static/analysis-engine.js#L17) |
| `polygonArea` | function | [51](../app/static/analysis-engine.js#L51) |
| `convexHull` | function | [58](../app/static/analysis-engine.js#L58) |
| `canonicalCorners` | function | [66](../app/static/analysis-engine.js#L66) |
| `sampleRGBA` | function | [78](../app/static/analysis-engine.js#L78) |
| `resize` | function | [87](../app/static/analysis-engine.js#L87) |
| `warp` | function | [94](../app/static/analysis-engine.js#L94) |
| `boxMorph` | function | [106](../app/static/analysis-engine.js#L106) |
| `connected` | function | [112](../app/static/analysis-engine.js#L112) |
| `boundaryPoints` | function | [128](../app/static/analysis-engine.js#L128) |
| `detectPaper` | function | [133](../app/static/analysis-engine.js#L133) |
| `geometry` | function | [152](../app/static/analysis-engine.js#L152) |
| `mean` | function | [173](../app/static/analysis-engine.js#L173) |
| `coefficient` | function | [174](../app/static/analysis-engine.js#L174) |
| `median` | function | [175](../app/static/analysis-engine.js#L175) |
| `volumeMedian` | function | [176](../app/static/analysis-engine.js#L176) |
| `drawBox` | function | [177](../app/static/analysis-engine.js#L177) |
| `analyzeImageData` | function | [183](../app/static/analysis-engine.js#L183) |

### app/static/annotation.html

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `showMessage` | function | [104](../app/static/annotation.html#L104) |
| `clearMessage` | function | [104](../app/static/annotation.html#L104) |
| `authFetch` | function | [105](../app/static/annotation.html#L105) |
| `fetchJson` | function | [111](../app/static/annotation.html#L111) |
| `updateAccess` | function | [122](../app/static/annotation.html#L122) |
| `connectDataset` | function | [129](../app/static/annotation.html#L129) |
| `disconnectDataset` | function | [145](../app/static/annotation.html#L145) |
| `setZoom` | function | [156](../app/static/annotation.html#L156) |
| `getCanvasPoint` | function | [157](../app/static/annotation.html#L157) |
| `annotationAt` | function | [158](../app/static/annotation.html#L158) |
| `currentTool` | function | [159](../app/static/annotation.html#L159) |
| `selectTool` | function | [159](../app/static/annotation.html#L159) |
| `className` | function | [160](../app/static/annotation.html#L160) |
| `colorFor` | function | [161](../app/static/annotation.html#L161) |
| `renderCanvas` | function | [162](../app/static/annotation.html#L162) |
| `renderStats` | function | [163](../app/static/annotation.html#L163) |
| `renderImageList` | function | [164](../app/static/annotation.html#L164) |
| `renderAnnotationList` | function | [175](../app/static/annotation.html#L175) |
| `physicalScale` | function | [194](../app/static/annotation.html#L194) |
| `updateDensity` | function | [198](../app/static/annotation.html#L198) |
| `getPixel` | function | [205](../app/static/annotation.html#L205) |
| `colorDistance` | function | [205](../app/static/annotation.html#L205) |
| `sampleRing` | function | [206](../app/static/annotation.html#L206) |
| `estimateRadiusFromColor` | function | [207](../app/static/annotation.html#L207) |
| `buildAnnotation` | function | [208](../app/static/annotation.html#L208) |
| `addAnnotation` | function | [209](../app/static/annotation.html#L209) |
| `brushDirt` | function | [209](../app/static/annotation.html#L209) |
| `loadImages` | function | [210](../app/static/annotation.html#L210) |
| `selectImage` | function | [220](../app/static/annotation.html#L220) |
| `saveAnnotations` | function | [245](../app/static/annotation.html#L245) |
| `reviewAnnotations` | function | [261](../app/static/annotation.html#L261) |
| `exportDataset` | function | [283](../app/static/annotation.html#L283) |
| `deleteAnnotation` | function | [284](../app/static/annotation.html#L284) |
| `pointerDown` | function | [285](../app/static/annotation.html#L285) |
| `pointerMove` | function | [286](../app/static/annotation.html#L286) |
| `pointerUp` | function | [286](../app/static/annotation.html#L286) |
| `clearAnnotations` | function | [287](../app/static/annotation.html#L287) |
| `openUploadModal` | function | [287](../app/static/annotation.html#L287) |
| `closeUploadModal` | function | [287](../app/static/annotation.html#L287) |
| `performUpload` | function | [288](../app/static/annotation.html#L288) |

### app/static/app.js

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `message` | function | [9](../app/static/app.js#L9) |
| `number` | function | [10](../app/static/app.js#L10) |
| `metric` | function | [11](../app/static/app.js#L11) |
| `date` | function | [18](../app/static/app.js#L18) |
| `age` | function | [19](../app/static/app.js#L19) |
| `cropKey` | function | [20](../app/static/app.js#L20) |
| `cropName` | function | [21](../app/static/app.js#L21) |
| `cropsFrom` | function | [22](../app/static/app.js#L22) |
| `renderCatalog` | function | [23](../app/static/app.js#L23) |
| `renderCrop` | function | [31](../app/static/app.js#L31) |
| `contextOrigin` | function | [42](../app/static/app.js#L42) |
| `renderContext` | function | [49](../app/static/app.js#L49) |
| `updateConnection` | function | [66](../app/static/app.js#L66) |
| `storageStatus` | function | [67](../app/static/app.js#L67) |
| `requestPersistence` | function | [71](../app/static/app.js#L71) |
| `coordinates` | function | [72](../app/static/app.js#L72) |
| `serverBase` | function | [78](../app/static/app.js#L78) |
| `syncContext` | function | [86](../app/static/app.js#L86) |
| `loadImage` | function | [104](../app/static/app.js#L104) |
| `drawInput` | function | [122](../app/static/app.js#L122) |
| `analysisOptions` | function | [132](../app/static/app.js#L132) |
| `workerAnalysis` | function | [142](../app/static/app.js#L142) |
| `analyze` | function | [153](../app/static/app.js#L153) |
| `cleanResult` | function | [178](../app/static/app.js#L178) |
| `renderOverlay` | function | [179](../app/static/app.js#L179) |
| `renderResult` | function | [188](../app/static/app.js#L188) |
| `renderHistory` | function | [202](../app/static/app.js#L202) |
| `exportResult` | function | [217](../app/static/app.js#L217) |
| `registerOffline` | function | [227](../app/static/app.js#L227) |
| `init` | function | [238](../app/static/app.js#L238) |

### app/static/offline-store.js

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `open` | function | [5](../app/static/offline-store.js#L5) |
| `transaction` | function | [16](../app/static/offline-store.js#L16) |

### app/utils/logger.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `setup_logging` | def | [13](../app/utils/logger.py#L13) |
| `log_function_call` | def | [43](../app/utils/logger.py#L43) |
| `log_api_call` | def | [49](../app/utils/logger.py#L49) |
| `log_error_with_context` | def | [59](../app/utils/logger.py#L59) |

### demo_ml_training.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `create_demo_image` | def | [17](../demo_ml_training.py#L17) |
| `test_image_analysis` | def | [97](../demo_ml_training.py#L97) |
| `test_api_upload` | async def | [129](../demo_ml_training.py#L129) |
| `test_annotation_api` | async def | [177](../demo_ml_training.py#L177) |
| `test_training_api` | async def | [216](../demo_ml_training.py#L216) |
| `test_statistics_api` | def | [261](../demo_ml_training.py#L261) |
| `run_complete_demo` | async def | [286](../demo_ml_training.py#L286) |
| `main` | def | [325](../demo_ml_training.py#L325) |

### install.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `check_python_version` | def | [11](../install.py#L11) |
| `install_dependencies` | def | [18](../install.py#L18) |
| `create_directories` | def | [28](../install.py#L28) |
| `setup_environment` | def | [41](../install.py#L41) |
| `run_tests` | def | [53](../install.py#L53) |
| `main` | def | [62](../install.py#L62) |

### main.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `lifespan` | async def | [45](../main.py#L45) |
| `create_app` | def | [63](../main.py#L63) |
| `create_app.favicon` | async def | [99](../main.py#L99) |
| `create_app.service_worker` | async def | [103](../main.py#L103) |
| `create_app.manifest` | async def | [111](../main.py#L111) |
| `create_app.app_icon` | async def | [115](../main.py#L115) |
| `create_app.read_root` | async def | [119](../main.py#L119) |
| `create_app.health_check` | async def | [131](../main.py#L131) |
| `create_app.readiness_check` | async def | [146](../main.py#L146) |
| `main` | def | [157](../main.py#L157) |

### scripts/evaluate_counts.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `evaluate` | def | [17](../scripts/evaluate_counts.py#L17) |
| `main` | def | [51](../scripts/evaluate_counts.py#L51) |

### scripts/sync_crop_catalog.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `main` | def | [9](../scripts/sync_crop_catalog.py#L9) |

### scripts/update_function_index.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `Declarations` | classe | [11](../scripts/update_function_index.py#L11) |
| `Declarations.__init__` | def | [12](../scripts/update_function_index.py#L12) |
| `Declarations.declaration` | def | [15](../scripts/update_function_index.py#L15) |
| `Declarations.visit_FunctionDef` | def | [31](../scripts/update_function_index.py#L31) |
| `Declarations.visit_AsyncFunctionDef` | def | [34](../scripts/update_function_index.py#L34) |
| `Declarations.visit_ClassDef` | def | [37](../scripts/update_function_index.py#L37) |
| `collect` | def | [41](../scripts/update_function_index.py#L41) |
| `main` | def | [61](../scripts/update_function_index.py#L61) |

### setup_ml_system.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `print_header` | def | [15](../setup_ml_system.py#L15) |
| `check_python_version` | def | [24](../setup_ml_system.py#L24) |
| `install_dependencies` | def | [36](../setup_ml_system.py#L36) |
| `create_directories` | def | [82](../setup_ml_system.py#L82) |
| `setup_database` | def | [102](../setup_ml_system.py#L102) |
| `create_sample_data` | def | [124](../setup_ml_system.py#L124) |
| `create_env_file` | def | [168](../setup_ml_system.py#L168) |
| `create_startup_script` | def | [206](../setup_ml_system.py#L206) |
| `test_system` | def | [228](../setup_ml_system.py#L228) |
| `test_fastapi` | def | [259](../setup_ml_system.py#L259) |
| `test_opencv` | def | [264](../setup_ml_system.py#L264) |
| `test_sklearn` | def | [274](../setup_ml_system.py#L274) |
| `test_database` | def | [288](../setup_ml_system.py#L288) |
| `test_image_analysis` | def | [305](../setup_ml_system.py#L305) |
| `print_success_message` | def | [315](../setup_ml_system.py#L315) |
| `main` | def | [344](../setup_ml_system.py#L344) |

### start.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `parse_args` | def | [18](../start.py#L18) |
| `get_lan_ip` | def | [38](../start.py#L38) |
| `print_urls` | def | [48](../start.py#L48) |
| `maybe_open_browser` | def | [78](../start.py#L78) |
| `main` | def | [84](../start.py#L84) |

### test_upload_single.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_upload` | def | [10](../test_upload_single.py#L10) |
| `main` | def | [38](../test_upload_single.py#L38) |

### tests/test_agriculture_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_normalize_crop_key_aliases` | def | [9](../tests/test_agriculture_service.py#L9) |
| `test_catalog_is_broad_and_does_not_invent_thresholds` | def | [17](../tests/test_agriculture_service.py#L17) |
| `test_culture_and_location_do_not_infer_soil_or_product` | def | [31](../tests/test_agriculture_service.py#L31) |
| `test_unknown_culture_remains_unknown` | def | [40](../tests/test_agriculture_service.py#L40) |

### tests/test_agrofit_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_agrofit_normalizes_product_record` | def | [6](../tests/test_agrofit_service.py#L6) |
| `test_agrofit_search_uses_local_cache` | def | [24](../tests/test_agrofit_service.py#L24) |

### tests/test_api_offline.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `client` | def | [12](../tests/test_api_offline.py#L12) |
| `_image` | def | [16](../tests/test_api_offline.py#L16) |
| `test_bootstrap_contains_complete_local_package_without_network` | def | [22](../tests/test_api_offline.py#L22) |
| `test_bootstrap_contains_complete_local_package_without_network.forbidden` | async def | [23](../tests/test_api_offline.py#L23) |
| `test_bootstrap_rejects_invalid_coordinates` | def | [40](../tests/test_api_offline.py#L40) |
| `test_server_analysis_without_gps_is_calibrated_only_when_confirmed` | def | [44](../tests/test_api_offline.py#L44) |
| `test_server_analysis_without_gps_is_calibrated_only_when_confirmed.analyze` | def | [46](../tests/test_api_offline.py#L46) |
| `test_server_analysis_without_gps_is_calibrated_only_when_confirmed.forbidden` | async def | [50](../tests/test_api_offline.py#L50) |
| `test_invalid_photo_and_profile_fail_before_processing` | def | [65](../tests/test_api_offline.py#L65) |
| `test_dataset_and_agrofit_writes_are_private_by_default` | def | [73](../tests/test_api_offline.py#L73) |
| `test_runtime_stats_do_not_invent_model_accuracy` | def | [78](../tests/test_api_offline.py#L78) |
| `test_preview_is_explicit_simulation_without_pesticide` | def | [84](../tests/test_api_offline.py#L84) |

### tests/test_catalog_bundle.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_bundled_catalogue_matches_canonical_source` | def | [5](../tests/test_catalog_bundle.py#L5) |

### tests/test_count_evaluation.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_human_count_report_preserves_bias_and_does_not_invent_detection_accuracy` | def | [8](../tests/test_count_evaluation.py#L8) |
| `test_human_count_report_preserves_bias_and_does_not_invent_detection_accuracy.Analyzer` | classe | [15](../tests/test_count_evaluation.py#L15) |
| `test_human_count_report_preserves_bias_and_does_not_invent_detection_accuracy.Analyzer.process_image` | def | [16](../tests/test_count_evaluation.py#L16) |
| `test_unfilled_example_cannot_be_reported_as_measured_ground_truth` | def | [25](../tests/test_count_evaluation.py#L25) |

### tests/test_dataset_integrity.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `dataset` | def | [21](../tests/test_dataset_integrity.py#L21) |
| `dataset.isolated_db` | def | [38](../tests/test_dataset_integrity.py#L38) |
| `_annotations` | def | [47](../tests/test_dataset_integrity.py#L47) |
| `_save` | def | [53](../tests/test_dataset_integrity.py#L53) |
| `_review` | def | [57](../tests/test_dataset_integrity.py#L57) |
| `test_private_dataset_and_image_require_header_and_enabled_server` | def | [61](../tests/test_dataset_integrity.py#L61) |
| `test_upload_normalizes_phone_exif_and_strips_metadata` | def | [73](../tests/test_dataset_integrity.py#L73) |
| `test_invalid_upload_leaves_no_orphan_file` | def | [93](../tests/test_dataset_integrity.py#L93) |
| `test_invalid_replacement_never_deletes_existing_annotations` | def | [108](../tests/test_dataset_integrity.py#L108) |
| `test_invalid_scale_preserves_annotations_and_saved_calibration` | def | [116](../tests/test_dataset_integrity.py#L116) |
| `test_save_preserves_zero_confidence_scale_and_pending_review` | def | [125](../tests/test_dataset_integrity.py#L125) |
| `test_review_validates_only_after_all_annotations_approved` | def | [144](../tests/test_dataset_integrity.py#L144) |
| `test_unknown_review_status_does_not_change_pending_annotation` | def | [160](../tests/test_dataset_integrity.py#L160) |
| `test_training_cli_failure_is_not_reported_as_success` | def | [166](../tests/test_dataset_integrity.py#L166) |
| `test_training_cli_failure_is_not_reported_as_success.post` | def | [170](../tests/test_dataset_integrity.py#L170) |
| `test_training_cli_failure_is_not_reported_as_success.get` | def | [173](../tests/test_dataset_integrity.py#L173) |
| `test_upload_clients_use_real_mime_single_case_insensitive_listing_and_private_header` | def | [183](../tests/test_dataset_integrity.py#L183) |
| `test_upload_clients_use_real_mime_single_case_insensitive_listing_and_private_header.post` | def | [194](../tests/test_dataset_integrity.py#L194) |

### tests/test_environmental_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_soil_units_and_uncertainty_are_explicit` | def | [8](../tests/test_environmental_service.py#L8) |
| `test_failed_soil_and_terrain_are_explicit_and_cached` | def | [22](../tests/test_environmental_service.py#L22) |
| `test_failed_soil_and_terrain_are_explicit_and_cached.offline` | async def | [26](../tests/test_environmental_service.py#L26) |
| `test_terrain_reports_dem_not_surveyed_slope` | def | [42](../tests/test_environmental_service.py#L42) |
| `test_terrain_reports_dem_not_surveyed_slope.response` | async def | [45](../tests/test_environmental_service.py#L45) |
| `test_invalid_coordinates_do_not_call_provider` | def | [56](../tests/test_environmental_service.py#L56) |
| `test_soil_budget_caps_requests_for_new_locations` | def | [67](../tests/test_environmental_service.py#L67) |
| `test_soil_budget_caps_requests_for_new_locations.response` | async def | [71](../tests/test_environmental_service.py#L71) |
| `test_soil_budget_caps_requests_for_new_locations.fetch_many` | async def | [79](../tests/test_environmental_service.py#L79) |

### tests/test_image_analysis.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `analyzer` | def | [19](../tests/test_image_analysis.py#L19) |
| `collector` | def | [24](../tests/test_image_analysis.py#L24) |
| `analyze` | def | [35](../tests/test_image_analysis.py#L35) |
| `test_counts_exclude_merged_edge_and_unresolved_stains` | def | [40](../tests/test_image_analysis.py#L40) |
| `test_coverage_is_observed_stain_pixels_without_expansion` | def | [51](../tests/test_image_analysis.py#L51) |
| `test_missing_calibration_never_invents_physical_units_or_quality` | def | [63](../tests/test_image_analysis.py#L63) |
| `test_physical_minimum_is_configurable_and_does_not_expand_coverage` | def | [74](../tests/test_image_analysis.py#L74) |
| `test_effective_minimum_reports_pixel_floor_and_cannot_create_missing_detail` | def | [81](../tests/test_image_analysis.py#L81) |
| `test_portrait_paper_retains_physical_long_axis` | def | [92](../tests/test_image_analysis.py#L92) |
| `test_spatial_cv_distinguishes_clustered_from_even_counts` | def | [107](../tests/test_image_analysis.py#L107) |
| `test_exif_orientation_applied_before_analysis` | def | [123](../tests/test_image_analysis.py#L123) |
| `test_invalid_path_and_invalid_corners` | def | [134](../tests/test_image_analysis.py#L134) |
| `test_invalid_explicit_scale_is_rejected_instead_of_assuming_default` | def | [146](../tests/test_image_analysis.py#L146) |
| `test_volume_proxy_uses_cubic_weights_not_number_median` | def | [151](../tests/test_image_analysis.py#L151) |
| `_node_runtime` | def | [155](../tests/test_image_analysis.py#L155) |
| `test_javascript_python_parity_for_counts_units_coverage_and_fuzzy` | def | [166](../tests/test_image_analysis.py#L166) |

### tests/test_ml_validation.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_patches_and_duplicate_source_images_never_cross_holdout` | def | [7](../tests/test_ml_validation.py#L7) |
| `test_duplicate_only_dataset_cannot_claim_independent_validation` | def | [16](../tests/test_ml_validation.py#L16) |

### tests/test_recommendation_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_deposition_never_infers_infestation_pesticide_or_dose` | def | [4](../tests/test_recommendation_service.py#L4) |
| `test_stale_or_mock_weather_never_authorizes_application` | def | [17](../tests/test_recommendation_service.py#L17) |

### tests/test_spray_quality.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `metrics` | def | [6](../tests/test_spray_quality.py#L6) |
| `test_fuzzy_requires_scale_and_shows_profile_and_rules` | def | [12](../tests/test_spray_quality.py#L12) |
| `test_confirmed_profile_is_indicative_not_a_claim_of_efficacy` | def | [22](../tests/test_spray_quality.py#L22) |
| `test_limiting_spatial_and_coalescence_reduce_membership` | def | [30](../tests/test_spray_quality.py#L30) |
| `test_invalid_profile_does_not_silently_change_thresholds` | def | [39](../tests/test_spray_quality.py#L39) |
| `test_unvalidated_catalog_profile_has_explicit_experimental_fallback` | def | [45](../tests/test_spray_quality.py#L45) |
| `test_malformed_or_partial_null_custom_profile_is_insufficient` | def | [59](../tests/test_spray_quality.py#L59) |

### tests/test_vision_features.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_extract_patch_features_includes_color_and_morphology` | def | [9](../tests/test_vision_features.py#L9) |

### tests/test_weather_service.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `test_analyze_spray_conditions_identifies_ideal_window` | def | [9](../tests/test_weather_service.py#L9) |
| `test_merge_daily_forecasts_preserves_priority_text` | def | [24](../tests/test_weather_service.py#L24) |
| `test_missing_weather_never_becomes_a_favorable_window` | def | [65](../tests/test_weather_service.py#L65) |
| `test_unavailable_weather_has_null_measurements` | def | [71](../tests/test_weather_service.py#L71) |
| `test_unavailable_weather_has_null_measurements.fail` | async def | [75](../tests/test_weather_service.py#L75) |
| `test_open_meteo_current_and_forecast_share_request` | def | [88](../tests/test_weather_service.py#L88) |
| `test_open_meteo_current_and_forecast_share_request.response` | async def | [93](../tests/test_weather_service.py#L93) |
| `test_snapshot_survives_restart_and_failed_refresh` | def | [114](../tests/test_weather_service.py#L114) |
| `test_snapshot_survives_restart_and_failed_refresh.online` | async def | [120](../tests/test_weather_service.py#L120) |
| `test_snapshot_survives_restart_and_failed_refresh.offline` | async def | [128](../tests/test_weather_service.py#L128) |
| `test_concurrent_snapshot_requests_share_provider_and_keep_source` | def | [141](../tests/test_weather_service.py#L141) |
| `test_concurrent_snapshot_requests_share_provider_and_keep_source.provider` | async def | [145](../tests/test_weather_service.py#L145) |
| `test_concurrent_snapshot_requests_share_provider_and_keep_source.fetch_pair` | async def | [150](../tests/test_weather_service.py#L150) |

### train_model.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_headers` | def | [12](../train_model.py#L12) |
| `check_dataset_ready` | def | [17](../train_model.py#L17) |
| `monitor_training` | def | [36](../train_model.py#L36) |
| `start_training` | def | [71](../train_model.py#L71) |
| `main` | def | [89](../train_model.py#L89) |

### upload_images.py

| Declaração | Tipo | Linha |
| --- | --- | ---: |
| `_headers` | def | [15](../upload_images.py#L15) |
| `image_mime` | def | [20](../upload_images.py#L20) |
| `list_images` | def | [27](../upload_images.py#L27) |
| `upload_images` | def | [39](../upload_images.py#L39) |
| `main` | def | [65](../upload_images.py#L65) |
