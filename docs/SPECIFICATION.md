# dbt-neo4j Adapter — 仕様ドラフト v0.1

> **ステータス**: Draft  
> **最終更新**: 2026-06-26  
> **対象 dbt バージョン**: dbt Core v2.0 (Fusion engine)  
> **対象 Neo4j バージョン**: Neo4j 5.x / Aura  
> **クエリ言語**: Cypher  

---

## 1. 概要

`dbt-neo4j` は、dbt のトランスフォーメーションパイプラインを Neo4j グラフデータベースに適用するためのコミュニティアダプタである。従来の RDB/DWH 向け dbt アダプタが「テーブル → テーブル」の変換を行うのに対し、本アダプタは以下の 3 つのコア機能を提供する：

1. **RDB to Graph** — リレーショナルデータをグラフ構造（Node / Relationship）に変換
2. **Graph Manipulation** — グラフ上での直接的なデータ変換・集約・拡張
3. **Graph Versioning** — グラフスキーマとデータの変更を追跡・管理

### 1.1 スコープ外（将来拡張）

以下の機能は本仕様の対象外とし、将来バージョンで検討する：

- **GraphRAG** — グラフベースの Retrieval-Augmented Generation
- **Graph Data Science** — Neo4j GDS ライブラリとの統合（PageRank, Community Detection 等）

ただし、これらの将来機能を見据え、**Embedding (Vector) 型のプロパティサポート**は本バージョンから対応する。

---

## 2. アーキテクチャ概要

本アダプタは **単一 dbt プロジェクト内でのデュアルアダプタ構成** を推奨する。DuckDB 上で SQL ベースのリレーショナル変換（staging / intermediate）を行い、最終モデルで Neo4j にグラフとして書き出す多段パイプラインである。

```
┌─────────────────────── 単一 dbt プロジェクト ───────────────────────┐
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Phase 1: SQL Transform (dbt-duckdb)                      │    │
│  │                                                            │    │
│  │  sources.yml ──► staging/ ──► intermediate/ ──► marts/     │    │
│  │  (raw data)     (clean)      (join/enrich)    (graph-ready)│    │
│  │                                                            │    │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────────────┐       │    │
│  │  │employees │──►│stg_emp   │──►│int_emp_dept_flat │       │    │
│  │  │departments│  │stg_dept  │   │int_emp_hierarchy │       │    │
│  │  │products  │   │stg_prod  │   │int_purchase_edges│       │    │
│  │  └──────────┘   └──────────┘   └────────┬─────────┘       │    │
│  └─────────────────────────────────────────│──────────────────┘    │
│                                             │                      │
│                                             ▼                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Phase 2: Graph Materialization (dbt-neo4j)               │    │
│  │                                                            │    │
│  │  graph_nodes/ ──────────► Neo4j Nodes                     │    │
│  │  graph_relationships/ ──► Neo4j Relationships             │    │
│  │  graph_transforms/ ─────► Cypher 操作                      │    │
│  │  graph_snapshots/ ──────► Graph Versioning                │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
└───────────────────────────────┬────────────────────────────────────┘
                                │
          ┌─────────────────────▼─────────────────────┐
          │                                           │
          │   ┌─────────────┐    ┌─────────────────┐  │
          │   │   DuckDB    │    │     Neo4j       │  │
          │   │  (SQL/OLAP) │    │  (Graph DB)     │  │
          │   │  staging    │    │  Nodes          │  │
          │   │  transform  │    │  Relationships  │  │
          │   │  .duckdb    │    │  Indexes        │  │
          │   └─────────────┘    │  Vector Indexes │  │
          │                      └─────────────────┘  │
          │           Data Layer                       │
          └────────────────────────────────────────────┘
```

**設計ポイント:**

- **Phase 1 (DuckDB)**: 既存の `dbt-duckdb` アダプタをそのまま活用。データクレンジング、結合、集約など SQL で表現しやすい変換をここで完了させる
- **Phase 2 (Neo4j)**: `dbt-neo4j` アダプタが Phase 1 の出力を読み取り、グラフ構造に変換して Neo4j に書き出す
- **単一プロジェクト**: `profiles.yml` に DuckDB と Neo4j の両方のターゲットを定義し、モデルごとに使用アダプタを切り替える

---

## 3. 接続設定 (`profiles.yml`)

```yaml
dbt_neo4j_project:
  target: dev
  outputs:
    dev:
      type: neo4j
      # 接続方式
      scheme: neo4j+s          # neo4j / neo4j+s / neo4j+ssc / bolt / bolt+s / bolt+ssc
      host: localhost
      port: 7687
      database: neo4j          # Neo4j 4.x+ マルチデータベース対応
      
      # 認証
      auth_type: basic         # basic / kerberos / bearer / custom
      user: neo4j
      password: "{{ env_var('NEO4J_PASSWORD') }}"
      
      # オプション
      encrypted: true
      trust: TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
      connection_timeout: 30   # 秒
      max_connection_lifetime: 3600
      max_connection_pool_size: 100
      connection_acquisition_timeout: 60
      
      # Aura 対応
      # scheme: neo4j+s
      # host: xxxxxxxx.databases.neo4j.io
      
      # バージョニング設定
      graph_versioning:
        enabled: true
        metadata_database: _dbt_meta  # メタデータ格納先
```

---

## 4. コア機能仕様

### 4.1 RDB to Graph（リレーショナル → グラフ変換）

#### 4.1.1 設計思想

RDB のテーブル / ビューからグラフ構造への変換を宣言的に定義する。dbt の `model` 概念を拡張し、以下のマテリアライゼーション・タイプを導入する：

| Materialization | 説明 | 生成対象 |
|---|---|---|
| `node` | RDB の行を Neo4j Node に変換 | `(:Label {props})` |
| `relationship` | RDB の行（FK 結合等）を Relationship に変換 | `()-[:TYPE {props}]->()` |
| `graph` | 複合グラフパターンの一括生成 | Nodes + Relationships |

#### 4.1.2 Node モデル

```sql
-- models/nodes/person.sql
{{
  config(
    materialized='node',
    labels=['Person', 'Employee'],          -- 複数ラベル対応
    unique_key='employee_id',               -- MERGE キー
    indexes=[
      {'properties': ['email'], 'type': 'range'},
      {'properties': ['name'], 'type': 'text'},
      {'properties': ['bio_embedding'], 'type': 'vector', 
       'dimensions': 1536, 'similarity_function': 'cosine'}
    ],
    constraints=[
      {'type': 'unique', 'properties': ['employee_id']},
      {'type': 'not_null', 'properties': ['name', 'email']},
      {'type': 'property_type', 'property': 'age', 'property_type': 'INTEGER'}
    ],
    strategy='merge'  -- merge / create / replace
  )
}}

SELECT
  employee_id,
  name,
  email,
  age,
  department_id,
  hire_date,
  bio_embedding          -- FLOAT[] として渡す → Vector プロパティ化
FROM {{ source('hr_system', 'employees') }}
WHERE active = true
```

**生成される Cypher:**

```cypher
// Constraints (事前実行)
CREATE CONSTRAINT person_unique_employee_id IF NOT EXISTS
  FOR (n:Person) REQUIRE n.employee_id IS UNIQUE;
CREATE CONSTRAINT person_not_null_name IF NOT EXISTS
  FOR (n:Person) REQUIRE n.name IS NOT NULL;

// Vector Index
CREATE VECTOR INDEX person_bio_embedding IF NOT EXISTS
  FOR (n:Person) ON (n.bio_embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }};

// Data Load (UNWIND batch)
UNWIND $batch AS row
MERGE (n:Person:Employee {employee_id: row.employee_id})
SET n.name = row.name,
    n.email = row.email,
    n.age = row.age,
    n.department_id = row.department_id,
    n.hire_date = date(row.hire_date),
    n.bio_embedding = row.bio_embedding,
    n._dbt_loaded_at = datetime()
```

#### 4.1.3 Relationship モデル

```sql
-- models/relationships/works_in.sql
{{
  config(
    materialized='relationship',
    relationship_type='WORKS_IN',
    source_node={
      'labels': ['Person'],
      'key': 'employee_id',
      'column': 'employee_id'
    },
    target_node={
      'labels': ['Department'],
      'key': 'department_id',
      'column': 'department_id'
    },
    strategy='merge',
    unique_key=['employee_id', 'department_id']
  )
}}

SELECT
  e.employee_id,
  e.department_id,
  e.hire_date AS since,
  e.role
FROM {{ source('hr_system', 'employees') }} e
WHERE e.department_id IS NOT NULL
```

**生成される Cypher:**

```cypher
UNWIND $batch AS row
MATCH (src:Person {employee_id: row.employee_id})
MATCH (tgt:Department {department_id: row.department_id})
MERGE (src)-[r:WORKS_IN]->(tgt)
SET r.since = date(row.since),
    r.role = row.role,
    r._dbt_loaded_at = datetime()
```

#### 4.1.4 Graph モデル（複合パターン）

```sql
-- models/graph/org_chart.sql
{{
  config(
    materialized='graph',
    patterns=[
      {
        'type': 'node',
        'labels': ['Manager'],
        'key': 'manager_id',
        'properties': ['name', 'level']
      },
      {
        'type': 'relationship',
        'relationship_type': 'REPORTS_TO',
        'source': {'labels': ['Person'], 'key': 'employee_id'},
        'target': {'labels': ['Manager'], 'key': 'manager_id'},
        'properties': ['since']
      }
    ]
  )
}}

SELECT
  e.employee_id,
  m.employee_id AS manager_id,
  m.name AS manager_name,
  m.management_level AS level,
  e.hire_date AS since
FROM {{ source('hr_system', 'employees') }} e
JOIN {{ source('hr_system', 'employees') }} m 
  ON e.manager_id = m.employee_id
```

---

### 4.2 Graph Manipulation（グラフ操作）

#### 4.2.1 設計思想

既存のグラフデータに対して Cypher ベースのトランスフォーメーションを実行する。dbt の `model` として定義し、入力も出力もグラフである。

#### 4.2.2 Cypher モデル（新規マテリアライゼーション）

| Materialization | 説明 | 用途 |
|---|---|---|
| `cypher` | 任意の Cypher クエリを実行 | グラフ変換全般 |
| `cypher_incremental` | 差分実行付き Cypher | 大規模グラフの差分更新 |

```sql
-- models/transformations/enrich_person_connections.sql
{{
  config(
    materialized='cypher',
    pre_hooks=[
      "CREATE INDEX person_department_idx IF NOT EXISTS FOR (n:Person) ON (n.department_id)"
    ]
  )
}}

// 同じ部署のメンバー間に COLLEAGUE 関係を作成
MATCH (a:Person)-[:WORKS_IN]->(d:Department)<-[:WORKS_IN]-(b:Person)
WHERE a <> b
  AND NOT EXISTS { (a)-[:COLLEAGUE]-(b) }
MERGE (a)-[r:COLLEAGUE]->(b)
SET r.department = d.name,
    r.created_at = datetime(),
    r._dbt_model = '{{ this.name }}'
```

#### 4.2.3 Incremental Cypher モデル

```sql
-- models/transformations/update_activity_score.sql
{{
  config(
    materialized='cypher_incremental',
    incremental_strategy='timestamp',
    incremental_key='_dbt_loaded_at',
    lookback_window='interval("P7D")'  -- 7日間のルックバック
  )
}}

MATCH (p:Person)
{% if is_incremental() %}
WHERE p._dbt_loaded_at > datetime() - duration('P7D')
{% endif %}
WITH p, size((p)-[:AUTHORED]->()) AS articles,
     size((p)-[:REVIEWED]->()) AS reviews
SET p.activity_score = articles * 2 + reviews,
    p._dbt_updated_at = datetime()
```

#### 4.2.4 Graph 操作マクロ

dbt-neo4j 固有の Jinja マクロを提供する：

| マクロ | 説明 | 用例 |
|---|---|---|
| `graph_merge_nodes()` | 複数 Node のマージ | 重複排除 |
| `graph_delete_orphans()` | 孤立ノードの削除 | クリーンアップ |
| `graph_set_labels()` | ラベルの追加・削除 | 分類変更 |
| `graph_copy_subgraph()` | サブグラフのコピー | スナップショット |
| `graph_shortest_path()` | 最短パス検索 | パス分析 |
| `graph_create_vector_index()` | ベクトルインデックス作成 | Embedding 検索 |
| `graph_vector_search()` | ベクトル類似検索 | 近似検索 |

```sql
-- マクロ使用例
{{ graph_merge_nodes(
     label='Person',
     merge_key='email',
     keep_strategy='newest',  -- newest / oldest / aggregate
     aggregate_properties={'login_count': 'sum', 'last_seen': 'max'}
) }}
```

---

### 4.3 Graph Versioning（グラフバージョニング）

#### 4.3.1 設計思想

グラフデータベースには DWH のような組み込みのスキーマバージョニング機構が存在しない。本アダプタでは以下の 3 層でバージョニングを実現する：

1. **Schema Versioning** — Node ラベル、Relationship タイプ、Constraint、Index の変更追跡
2. **Data Snapshot** — グラフデータの時点スナップショット
3. **Lineage Tracking** — dbt モデル間のデータ系譜をグラフ自体に記録

#### 4.3.2 Schema Versioning

```yaml
# models/nodes/person.yml
version: 2

models:
  - name: person
    description: "Person node model"
    config:
      materialized: node
      labels: ['Person', 'Employee']
    
    # スキーマバージョン管理
    schema_version:
      current: 3
      changelog:
        - version: 1
          date: 2026-01-15
          changes:
            - "Initial creation with basic properties"
        - version: 2
          date: 2026-03-01
          changes:
            - "Added bio_embedding property (FLOAT[], 1536 dimensions)"
            - "Created vector index on bio_embedding"
        - version: 3
          date: 2026-06-15
          changes:
            - "Added 'Employee' label"
            - "Added NOT NULL constraint on email"
      
      # マイグレーション定義
      migrations:
        - from_version: 1
          to_version: 2
          cypher: |
            MATCH (n:Person)
            WHERE n.bio_embedding IS NULL
            SET n.bio_embedding = []
        - from_version: 2
          to_version: 3
          cypher: |
            MATCH (n:Person)
            SET n:Employee
```

#### 4.3.3 Data Snapshot

dbt の `snapshot` 機能をグラフ向けに拡張する：

```sql
-- snapshots/person_snapshot.sql
{% snapshot person_snapshot %}

{{
  config(
    target_labels=['Person'],
    unique_key='employee_id',
    strategy='timestamp',
    updated_at='updated_at',
    snapshot_label='PersonSnapshot',         -- スナップショット用ラベル
    snapshot_relationship='HAS_SNAPSHOT',    -- 元ノードとの関係
    invalidate_hard_deletes=True
  )
}}

MATCH (n:Person)
RETURN n.employee_id AS employee_id,
       n.name AS name,
       n.email AS email,
       n.department_id AS department_id,
       n.updated_at AS updated_at

{% endsnapshot %}
```

**スナップショットグラフ構造:**

```
(:Person {employee_id: 1})
  -[:HAS_SNAPSHOT {dbt_valid_from, dbt_valid_to}]->
(:PersonSnapshot {employee_id: 1, name: "旧名前", ...})
```

#### 4.3.4 Lineage Tracking（系譜追跡）

dbt の実行メタデータをグラフ内に `_dbt_*` プレフィックスのメタデータとして記録する：

```
(:_DbtModel {name: 'person', materialized: 'node', run_id: '...'})
  -[:_DBT_PRODUCES]->
(:_DbtRelation {labels: ['Person'], database: 'neo4j'})

(:_DbtModel {name: 'works_in'})
  -[:_DBT_DEPENDS_ON]->
(:_DbtModel {name: 'person'})
```

**各ノード/リレーションシップに自動付与されるメタプロパティ:**

| プロパティ | 型 | 説明 |
|---|---|---|
| `_dbt_loaded_at` | `ZONED DATETIME` | データロード日時 |
| `_dbt_updated_at` | `ZONED DATETIME` | 最終更新日時 |
| `_dbt_model` | `STRING` | ソースモデル名 |
| `_dbt_run_id` | `STRING` | dbt 実行 ID |
| `_dbt_schema_version` | `INTEGER` | スキーマバージョン |

---

## 5. データ型マッピング

### 5.1 Neo4j プロパティ型（全対応）

Neo4j の Cypher が対応するすべてのプロパティ型をサポートする：

| カテゴリ | Neo4j 型 | dbt-neo4j 表記 | SQL/Python 変換元 | 備考 |
|---|---|---|---|---|
| **ブール** | `BOOLEAN` | `boolean` | `BOOL`, `bool` | |
| **整数** | `INTEGER` | `integer` | `INT`, `BIGINT`, `int` | 64-bit 符号付き整数 |
| **浮動小数点** | `FLOAT` | `float` | `DOUBLE`, `REAL`, `float` | 64-bit IEEE 754 |
| **文字列** | `STRING` | `string` | `VARCHAR`, `TEXT`, `str` | |
| **日付** | `DATE` | `date` | `DATE` | ISO 8601 |
| **時刻（TZ付き）** | `ZONED TIME` | `zoned_time` | `TIMETZ` | |
| **時刻（ローカル）** | `LOCAL TIME` | `local_time` | `TIME` | |
| **日時（TZ付き）** | `ZONED DATETIME` | `zoned_datetime` | `TIMESTAMPTZ` | |
| **日時（ローカル）** | `LOCAL DATETIME` | `local_datetime` | `TIMESTAMP` | |
| **期間** | `DURATION` | `duration` | `INTERVAL` | ISO 8601 Duration |
| **座標（2D）** | `POINT (Cartesian)` | `point_2d` | カスタム | `{x, y}` |
| **座標（3D）** | `POINT (Cartesian 3D)` | `point_3d` | カスタム | `{x, y, z}` |
| **座標（WGS-84）** | `POINT (WGS-84)` | `point_wgs84` | `GEOGRAPHY` | `{latitude, longitude}` |
| **座標（WGS-84 3D）** | `POINT (WGS-84 3D)` | `point_wgs84_3d` | カスタム | `{lat, lon, height}` |
| **リスト** | `LIST<T>` | `list<T>` | `ARRAY` | 同一型の要素 |
| **マップ** | `MAP` | `map` | `JSON`, `JSONB` | キーバリュー |

### 5.2 Embedding / Vector 型

Neo4j 5.11+ で導入された Vector 型を第一級市民としてサポートする：

| 機能 | 型 / 構文 | 説明 |
|---|---|---|
| **ストレージ** | `LIST<FLOAT>` (プロパティ) | ベクトルデータの保存 |
| **インデックス** | `VECTOR INDEX` | ANN (Approximate Nearest Neighbor) 検索 |
| **類似度関数** | `cosine` / `euclidean` | 距離計算方式 |
| **検索** | `vector.similarity.cosine()` | ベクトル類似検索関数 |
| **次元数** | 設定可能 (1〜4096) | モデル依存 |

**Embedding プロパティの定義例:**

```yaml
# schema.yml
models:
  - name: document_node
    columns:
      - name: content_embedding
        data_type: "list<float>"
        description: "OpenAI text-embedding-3-small (1536 dims)"
        meta:
          neo4j:
            vector_index:
              enabled: true
              dimensions: 1536
              similarity_function: cosine
      - name: image_embedding
        data_type: "list<float>"
        description: "CLIP ViT-B/32 image embedding (512 dims)"
        meta:
          neo4j:
            vector_index:
              enabled: true
              dimensions: 512
              similarity_function: euclidean
```

**Vector Index 作成 Cypher:**

```cypher
CREATE VECTOR INDEX document_content_embedding IF NOT EXISTS
FOR (n:Document)
ON (n.content_embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine',
    `vector.quantization.enabled`: false
  }
}
```

---

## 6. dbt 標準機能のグラフ適応

### 6.1 Materializations マッピング

| dbt 標準 | dbt-neo4j 対応 | 説明 |
|---|---|---|
| `table` | `node` | Node を作成（`CREATE` or full replace） |
| `view` | `cypher_view` | 保存された Cypher クエリ（実行時評価） |
| `incremental` | `node_incremental` / `relationship_incremental` | 差分更新 |
| `ephemeral` | `ephemeral` | CTEとして他モデルに埋め込み |
| `snapshot` | `graph_snapshot` | ノード/リレーションシップのスナップショット |
| *(new)* | `relationship` | Relationship を作成 |
| *(new)* | `graph` | 複合グラフパターン |
| *(new)* | `cypher` | 任意 Cypher 実行 |

### 6.2 Tests（テスト）

#### Schema Tests

```yaml
models:
  - name: person
    columns:
      - name: employee_id
        tests:
          - unique            # Node のプロパティ一意性
          - not_null          # NULL 非許容
      - name: email
        tests:
          - unique
          - accepted_values:
              values: ['@company.com']  # ドメインチェック（suffix）
              match_type: suffix
```

#### Graph-Specific Tests（グラフ固有テスト）

| テスト名 | 説明 | 例 |
|---|---|---|
| `graph_connected` | 孤立ノードがないことを検証 | `Person` は必ず `WORKS_IN` を持つ |
| `graph_no_self_loop` | 自己ループがないことを検証 | `Person` -[COLLEAGUE]-> 自分自身 |
| `graph_relationship_cardinality` | 関係の基数チェック | 1人は1つの `Department` に所属 |
| `graph_path_exists` | 特定パスの存在確認 | CEO からの報告チェーン |
| `graph_label_consistency` | ラベル整合性 | `Employee` は必ず `Person` も持つ |
| `graph_property_type` | プロパティ型の検証 | `age` は `INTEGER` |
| `graph_vector_dimensions` | ベクトル次元数の検証 | embedding は 1536 次元 |

```yaml
# tests/graph_tests.yml
tests:
  - name: person_must_have_department
    test_type: graph_connected
    config:
      node_label: Person
      relationship_type: WORKS_IN
      direction: outgoing
      min_degree: 1

  - name: no_self_reporting
    test_type: graph_no_self_loop
    config:
      relationship_type: REPORTS_TO
```

### 6.3 Sources（ソース）

RDB ソースと Neo4j ソースの両方をサポート：

```yaml
sources:
  # RDB ソース（既存のリレーショナル DB）
  - name: hr_system
    type: postgres         # 任意の dbt サポートDB
    database: hr_db
    schema: public
    tables:
      - name: employees
      - name: departments

  # Neo4j ソース（既存のグラフ）
  - name: existing_graph
    type: neo4j
    database: neo4j
    nodes:
      - name: Customer
        identifier: Customer    # ラベル名
        loaded_at_field: _dbt_loaded_at
    relationships:
      - name: PURCHASED
        identifier: PURCHASED   # Relationship Type
```

### 6.4 Seeds

CSV シードデータを Neo4j にロードする：

```yaml
# dbt_project.yml
seeds:
  dbt_neo4j_project:
    country_codes:
      +materialized: node
      +labels: ['Country']
      +unique_key: code
```

### 6.5 Hooks

```yaml
# dbt_project.yml
on-run-start:
  - "CREATE CONSTRAINT IF NOT EXISTS FOR (n:_DbtRun) REQUIRE n.run_id IS UNIQUE"

on-run-end:
  - "{{ graph_delete_orphans(label='_DbtRunArtifact', older_than='P30D') }}"
```

---

## 7. バッチ処理とパフォーマンス

### 7.1 バッチ戦略

大規模データのロードでは、Cypher の `UNWIND` とパラメータ化クエリを使用：

```yaml
# dbt_project.yml
vars:
  neo4j_batch_size: 10000        # 1バッチあたりの行数
  neo4j_parallel_workers: 4      # 並列ワーカー数
  neo4j_transaction_timeout: 600 # トランザクションタイムアウト（秒）
  neo4j_retry_on_failure: true   # 失敗時リトライ
  neo4j_max_retries: 3           # 最大リトライ回数
```

### 7.2 CALL IN TRANSACTIONS

大規模変更操作では `CALL { ... } IN TRANSACTIONS` を自動利用：

```cypher
CALL {
  UNWIND $batch AS row
  MERGE (n:Person {employee_id: row.employee_id})
  SET n += row.properties
} IN TRANSACTIONS OF 10000 ROWS
```

### 7.3 Index-Aware Optimization

`MERGE` 操作前に対応するインデックス・制約の存在を自動確認し、パフォーマンスを最適化：

```
[INFO] Checking indexes for (:Person) on [employee_id]...
[INFO] Index found: person_employee_id_unique (UNIQUENESS)
[INFO] Executing MERGE with index-backed lookup
```

---

## 8. エラーハンドリングとログ

### 8.1 Neo4j 固有エラーの分類

| Neo4j エラーコード | dbt 分類 | 対応 |
|---|---|---|
| `Neo.ClientError.Schema.ConstraintValidationFailed` | `DatabaseError` | ユーザーにデータ修正を促す |
| `Neo.TransientError.Transaction.DeadlockDetected` | `RetryableError` | 自動リトライ |
| `Neo.ClientError.Statement.SyntaxError` | `CompilationError` | Cypher 文法エラー表示 |
| `Neo.DatabaseError.General.OutOfMemoryError` | `InternalError` | バッチサイズ縮小を推奨 |

### 8.2 ログ出力

```
[INFO] Running node model: person (Labels: ['Person', 'Employee'])
[INFO] Strategy: merge (unique_key: employee_id)
[INFO] Processing 50,000 rows in 5 batches of 10,000
[INFO] Batch 1/5: MERGED 10,000 nodes (2.3s)
[INFO] Batch 2/5: MERGED 10,000 nodes (2.1s)
...
[INFO] Total: 50,000 nodes processed. Created: 5,000, Updated: 45,000
[INFO] Indexes verified: 3, Constraints verified: 2
```

---

## 9. ディレクトリ構造

```
dbt-neo4j/
├── dbt/
│   └── adapters/
│       └── neo4j/
│           ├── __init__.py
│           ├── connections.py        # Neo4j Bolt 接続管理
│           ├── relation.py           # GraphRelation (Node/Rel)
│           ├── column.py             # PropertyColumn
│           ├── impl.py               # Neo4jAdapter 本体
│           └── type_mapping.py       # 型変換ロジック
│
├── dbt/
│   └── include/
│       └── neo4j/
│           ├── dbt_project.yml
│           ├── macros/
│           │   ├── materializations/
│           │   │   ├── node.sql
│           │   │   ├── relationship.sql
│           │   │   ├── graph.sql
│           │   │   ├── cypher.sql
│           │   │   ├── cypher_incremental.sql
│           │   │   └── graph_snapshot.sql
│           │   ├── adapters/
│           │   │   ├── create_constraint.sql
│           │   │   ├── create_index.sql
│           │   │   ├── create_vector_index.sql
│           │   │   ├── drop_relation.sql
│           │   │   └── rename_relation.sql
│           │   ├── graph_operations/
│           │   │   ├── merge_nodes.sql
│           │   │   ├── delete_orphans.sql
│           │   │   ├── set_labels.sql
│           │   │   ├── copy_subgraph.sql
│           │   │   └── vector_search.sql
│           │   └── tests/
│           │       ├── graph_connected.sql
│           │       ├── graph_no_self_loop.sql
│           │       ├── graph_relationship_cardinality.sql
│           │       ├── graph_path_exists.sql
│           │       └── graph_vector_dimensions.sql
│           └── seeds/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── functional/
│
├── docs/
│   └── SPECIFICATION.md             # この文書
│
├── setup.py
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

---

## 10. 依存関係

### 10.1 dbt-neo4j アダプタの依存

| パッケージ | バージョン | 用途 |
|---|---|---|
| `dbt-core` | `>=2.0.0` | dbt フレームワーク |
| `neo4j` (Python Driver) | `>=5.0.0` | Bolt プロトコル接続 |
| `pyarrow` | `>=12.0.0` | バッチデータ転送 |

### 10.2 推奨パイプライン構成の依存

| パッケージ | バージョン | 用途 | リポジトリ |
|---|---|---|---|
| `dbt-duckdb` | `>=1.9.0` | Phase 1: SQL 変換エンジン（既存コミュニティアダプタ） | [duckdb/dbt-duckdb](https://github.com/duckdb/dbt-duckdb) |
| `duckdb` | `>=1.0.0` | DuckDB エンジン本体 | [duckdb/duckdb](https://github.com/duckdb/duckdb) |

---

## 11. 制約事項と既知の限界

### 11.1 Neo4j 固有の制約

1. **テーブル概念の不在**: Neo4j には「テーブル」がないため、dbt の `ref()` はラベルまたは Relationship Type を参照する
2. **スキーマレス性**: Neo4j は本質的にスキーマレスであるため、型強制は Constraint ベース
3. **トランザクションサイズ**: 大規模データロードはバッチ分割が必須
4. **マルチデータベース**: Enterprise Edition または Aura でのみマルチデータベース対応
5. **DDL トランザクション分離**: Index/Constraint 作成はデータ操作と同一トランザクションで実行不可

### 11.2 dbt 互換性の制限

1. **SQL パースの非互換**: Cypher は SQL ではないため、dbt の SQL パーサーをバイパスする必要がある
2. **カタログ生成**: `dbt docs generate` はグラフ構造をリレーショナルな形式に変換して表示
3. **Incremental モデル**: `delete+insert` 戦略はグラフでは `detach delete + create` に変換

---

## 12. Reference Architecture: DuckDB → Neo4j パイプライン

本セクションでは、DuckDB をリレーショナル変換エンジンとし、Neo4j をグラフ出力先とする推奨アーキテクチャの具体例を示す。

### 12.1 プロジェクト構成

```
my_graph_project/
├── dbt_project.yml
├── profiles.yml
├── packages.yml
│
├── seeds/
│   ├── country_codes.csv
│   └── product_categories.csv
│
├── models/
│   │
│   │── sources.yml                    # ソース定義（DuckDB 上の raw テーブル）
│   │
│   ├── staging/                       # Phase 1a: DuckDB (クレンジング)
│   │   ├── _staging.yml
│   │   ├── stg_employees.sql
│   │   ├── stg_departments.sql
│   │   ├── stg_products.sql
│   │   └── stg_purchases.sql
│   │
│   ├── intermediate/                  # Phase 1b: DuckDB (結合・正規化)
│   │   ├── _intermediate.yml
│   │   ├── int_employee_department.sql
│   │   ├── int_employee_hierarchy.sql
│   │   ├── int_customer_purchases.sql
│   │   └── int_product_embeddings.sql
│   │
│   ├── graph_nodes/                   # Phase 2a: Neo4j (Node 生成)
│   │   ├── _graph_nodes.yml
│   │   ├── person_node.sql
│   │   ├── department_node.sql
│   │   ├── product_node.sql
│   │   └── customer_node.sql
│   │
│   ├── graph_relationships/           # Phase 2b: Neo4j (Relationship 生成)
│   │   ├── _graph_relationships.yml
│   │   ├── works_in_rel.sql
│   │   ├── reports_to_rel.sql
│   │   ├── purchased_rel.sql
│   │   └── similar_to_rel.sql
│   │
│   └── graph_transforms/              # Phase 2c: Neo4j (Cypher 変換)
│       ├── _graph_transforms.yml
│       ├── enrich_colleagues.sql
│       └── compute_centrality_label.sql
│
├── snapshots/
│   └── person_snapshot.sql
│
└── tests/
    ├── generic/
    └── graph/
```

### 12.2 `packages.yml` — アダプタ依存の宣言

`dbt-duckdb` は既存のコミュニティアダプタ（[duckdb/dbt-duckdb](https://github.com/duckdb/dbt-duckdb)）をそのまま利用する。
`dbt-neo4j` は本プロジェクトで新規開発するアダプタである。

```yaml
# packages.yml
packages:
  # Phase 1: SQL 変換エンジン（既存コミュニティアダプタ）
  - package: duckdb/dbt-duckdb
    version: ">=1.9.0"

  # Phase 2: グラフ出力エンジン（本プロジェクトで開発）
  - git: https://github.com/<org>/dbt-neo4j.git
    revision: main
```

**インストール:**

```bash
# pip で両アダプタをインストール
pip install dbt-duckdb dbt-neo4j

# dbt deps でパッケージ依存を解決
dbt deps
```

### 12.3 `profiles.yml` — デュアルアダプタ設定

```yaml
my_graph_project:
  target: dev
  outputs:
    # Phase 1: SQL 変換用（DuckDB）
    dev:
      type: duckdb
      path: "{{ env_var('DBT_DUCKDB_PATH', 'data/warehouse.duckdb') }}"
      schema: main
      threads: 4

    # Phase 2: グラフ出力用（Neo4j）
    neo4j_dev:
      type: neo4j
      scheme: neo4j+s
      host: "{{ env_var('NEO4J_HOST', 'localhost') }}"
      port: 7687
      database: neo4j
      auth_type: basic
      user: neo4j
      password: "{{ env_var('NEO4J_PASSWORD') }}"
      encrypted: true
      graph_versioning:
        enabled: true
```

### 12.4 `dbt_project.yml` — モデルごとのアダプタ切替

```yaml
name: my_graph_project
version: '1.0.0'
config-version: 2

profile: my_graph_project

# モデルごとにターゲット（アダプタ）を切り替え
models:
  my_graph_project:
    # Phase 1: DuckDB で実行
    staging:
      +materialized: view
      +target: dev              # dbt-duckdb
    intermediate:
      +materialized: table
      +target: dev              # dbt-duckdb

    # Phase 2: Neo4j で実行
    graph_nodes:
      +materialized: node
      +target: neo4j_dev        # dbt-neo4j
    graph_relationships:
      +materialized: relationship
      +target: neo4j_dev        # dbt-neo4j
    graph_transforms:
      +materialized: cypher
      +target: neo4j_dev        # dbt-neo4j

vars:
  neo4j_batch_size: 10000
  neo4j_retry_on_failure: true
```

### 12.5 パイプライン実装例（End-to-End）

以下に、従業員データを DuckDB で変換し Neo4j にグラフ化する完全な例を示す。

#### Step 1: ソース定義

```yaml
# models/sources.yml
version: 2
sources:
  - name: hr_raw
    description: "HR システムから取得した生データ（DuckDB 上）"
    schema: raw
    tables:
      - name: employees
        description: "従業員マスタ"
        columns:
          - name: id
            tests: [unique, not_null]
          - name: name
          - name: email
          - name: department_id
          - name: manager_id
          - name: hire_date
          - name: bio
      - name: departments
        description: "部署マスタ"
      - name: purchases
        description: "購買履歴"
```

#### Step 2: Staging（DuckDB — クレンジング）

```sql
-- models/staging/stg_employees.sql
-- target: dbt-duckdb

WITH source AS (
    SELECT * FROM {{ source('hr_raw', 'employees') }}
)

SELECT
    id AS employee_id,
    TRIM(name) AS name,
    LOWER(TRIM(email)) AS email,
    department_id,
    manager_id,
    CAST(hire_date AS DATE) AS hire_date,
    COALESCE(bio, '') AS bio,
    -- タイムスタンプの正規化
    CURRENT_TIMESTAMP AS _loaded_at
FROM source
WHERE id IS NOT NULL
  AND name IS NOT NULL
```

#### Step 3: Intermediate（DuckDB — 結合・Embedding 準備）

```sql
-- models/intermediate/int_employee_department.sql
-- target: dbt-duckdb

WITH employees AS (
    SELECT * FROM {{ ref('stg_employees') }}
),

departments AS (
    SELECT * FROM {{ ref('stg_departments') }}
)

SELECT
    e.employee_id,
    e.name,
    e.email,
    e.hire_date,
    e.bio,
    e.manager_id,
    d.department_id,
    d.department_name,
    d.location,
    -- Graph 用の前処理: ラベル候補の決定
    CASE 
        WHEN e.manager_id IS NULL THEN 'Executive'
        WHEN EXISTS (
            SELECT 1 FROM {{ ref('stg_employees') }} sub 
            WHERE sub.manager_id = e.employee_id
        ) THEN 'Manager'
        ELSE 'Individual'
    END AS role_type,
    e._loaded_at
FROM employees e
LEFT JOIN departments d ON e.department_id = d.department_id
```

```sql
-- models/intermediate/int_employee_hierarchy.sql
-- target: dbt-duckdb
-- 上司-部下関係をフラット化（Relationship 用）

SELECT
    e.employee_id,
    e.manager_id,
    e.name AS employee_name,
    m.name AS manager_name,
    e.hire_date AS reporting_since,
    -- 直属かスキップレベルか
    'DIRECT' AS report_type
FROM {{ ref('stg_employees') }} e
INNER JOIN {{ ref('stg_employees') }} m
    ON e.manager_id = m.employee_id
WHERE e.manager_id IS NOT NULL
```

```sql
-- models/intermediate/int_product_embeddings.sql
-- target: dbt-duckdb
-- Embedding を事前計算して DuckDB に保持
-- （実際の Embedding 生成は外部 Python スクリプトまたは UDF で実施）

SELECT
    p.product_id,
    p.product_name,
    p.description,
    p.category,
    p.price,
    -- Embedding は事前計算済みのカラムとして存在する想定
    p.description_embedding   -- FLOAT[1536]
FROM {{ ref('stg_products') }} p
WHERE p.description_embedding IS NOT NULL
```

#### Step 4: Graph Nodes（Neo4j — ノード生成）

```sql
-- models/graph_nodes/person_node.sql
-- target: dbt-neo4j

{{
  config(
    materialized='node',
    labels=['Person'],
    unique_key='employee_id',
    indexes=[
      {'properties': ['email'], 'type': 'range'},
      {'properties': ['name'], 'type': 'text'}
    ],
    constraints=[
      {'type': 'unique', 'properties': ['employee_id']},
      {'type': 'not_null', 'properties': ['name', 'email']}
    ],
    strategy='merge'
  )
}}

-- DuckDB の intermediate モデルを cross-db ref で参照
SELECT
    employee_id,
    name,
    email,
    hire_date,
    bio,
    role_type
FROM {{ ref('int_employee_department') }}
```

```sql
-- models/graph_nodes/department_node.sql
-- target: dbt-neo4j

{{
  config(
    materialized='node',
    labels=['Department'],
    unique_key='department_id',
    constraints=[
      {'type': 'unique', 'properties': ['department_id']}
    ],
    strategy='merge'
  )
}}

SELECT DISTINCT
    department_id,
    department_name,
    location
FROM {{ ref('int_employee_department') }}
WHERE department_id IS NOT NULL
```

```sql
-- models/graph_nodes/product_node.sql
-- target: dbt-neo4j
-- Embedding 付き Node

{{
  config(
    materialized='node',
    labels=['Product'],
    unique_key='product_id',
    indexes=[
      {'properties': ['description_embedding'], 'type': 'vector',
       'dimensions': 1536, 'similarity_function': 'cosine'}
    ],
    strategy='merge'
  )
}}

SELECT
    product_id,
    product_name,
    description,
    category,
    price,
    description_embedding     -- LIST<FLOAT> → Neo4j Vector property
FROM {{ ref('int_product_embeddings') }}
```

#### Step 5: Graph Relationships（Neo4j — リレーションシップ生成）

```sql
-- models/graph_relationships/works_in_rel.sql
-- target: dbt-neo4j

{{
  config(
    materialized='relationship',
    relationship_type='WORKS_IN',
    source_node={
      'labels': ['Person'],
      'key': 'employee_id',
      'column': 'employee_id'
    },
    target_node={
      'labels': ['Department'],
      'key': 'department_id',
      'column': 'department_id'
    },
    strategy='merge'
  )
}}

SELECT
    employee_id,
    department_id,
    hire_date AS since
FROM {{ ref('int_employee_department') }}
WHERE department_id IS NOT NULL
```

```sql
-- models/graph_relationships/reports_to_rel.sql
-- target: dbt-neo4j

{{
  config(
    materialized='relationship',
    relationship_type='REPORTS_TO',
    source_node={
      'labels': ['Person'],
      'key': 'employee_id',
      'column': 'employee_id'
    },
    target_node={
      'labels': ['Person'],
      'key': 'employee_id',
      'column': 'manager_id'
    },
    strategy='merge'
  )
}}

SELECT
    employee_id,
    manager_id,
    reporting_since AS since,
    report_type
FROM {{ ref('int_employee_hierarchy') }}
```

#### Step 6: Graph Transforms（Neo4j — Cypher によるグラフ内変換）

```sql
-- models/graph_transforms/enrich_colleagues.sql
-- target: dbt-neo4j
-- Phase 2 完了後、グラフ内でさらに関係を推論

{{
  config(
    materialized='cypher',
    depends_on=[
      ref('person_node'),
      ref('works_in_rel')
    ]
  )
}}

// 同じ部署に所属するメンバー間に COLLEAGUE 関係を生成
MATCH (a:Person)-[:WORKS_IN]->(d:Department)<-[:WORKS_IN]-(b:Person)
WHERE a.employee_id < b.employee_id
  AND NOT EXISTS { (a)-[:COLLEAGUE]-(b) }
MERGE (a)-[r:COLLEAGUE]->(b)
SET r.department = d.department_name,
    r.created_at = datetime(),
    r._dbt_model = '{{ this.name }}'
```

#### Step 7: 実行フロー

```bash
# Phase 1: DuckDB 上の SQL 変換を実行
dbt run --target dev --select staging intermediate

# Phase 2: Neo4j へのグラフ出力を実行
dbt run --target neo4j_dev --select graph_nodes graph_relationships graph_transforms

# または一括実行（依存関係に従い自動順序決定）
dbt run

# テスト
dbt test

# スナップショット
dbt snapshot --target neo4j_dev
```

### 12.6 Cross-Database Reference（クロスDB参照）の仕組み

Phase 2 のモデル（Neo4j 向け）から Phase 1 のモデル（DuckDB 上）を参照するために、アダプタ内部では以下の処理を行う：

```
{{ ref('int_employee_department') }}  ← DuckDB 上の intermediate テーブル
         │
         ▼
┌─────────────────────────────────────────────┐
│ dbt-neo4j adapter 内部処理:                 │
│                                             │
│ 1. ref() が DuckDB ターゲットのモデルを解決  │
│ 2. DuckDB に SELECT クエリを発行            │
│ 3. 結果セットを Python オブジェクトに読込み  │
│ 4. バッチに分割                             │
│ 5. UNWIND $batch で Neo4j に MERGE          │
└─────────────────────────────────────────────┘
```

**内部的な実行イメージ:**

```python
# Pseudo-code: アダプタ内部のクロスDB参照処理
def execute_node_model(model, source_adapter, target_adapter):
    # 1. DuckDB からデータ読み取り
    rows = source_adapter.execute_sql(
        "SELECT * FROM int_employee_department"
    )
    
    # 2. バッチに分割
    for batch in chunk(rows, batch_size=10000):
        # 3. Cypher 生成 & 実行
        cypher = generate_merge_cypher(model.config, batch)
        target_adapter.execute_cypher(cypher, params={'batch': batch})
```

### 12.7 生成されるグラフ構造

上記パイプラインの実行後、Neo4j 上には以下のグラフが構築される：

```
                    ┌──────────────┐
                    │ :Department  │
                    │ {dept_id,    │
                    │  name,       │
                    │  location}   │
                    └──────▲───────┘
                           │
                     [:WORKS_IN]
                      {since}
                           │
┌─────────────┐    ┌───────┴───────┐    ┌─────────────┐
│ :Person     │◄───│   :Person     │───►│ :Person     │
│ (Manager)   │    │  {emp_id,     │    │ (Individual)│
│             │    │   name,       │    │             │
└──────▲──────┘    │   email,      │    └─────────────┘
       │           │   role_type}  │
  [:REPORTS_TO]    └───────┬───────┘
   {since,                 │
    report_type}     [:COLLEAGUE]
       │            {department}
       ▼                   │
┌──────────────┐    ┌──────▼───────┐
│ :Person      │    │  :Product    │
│ (Executive)  │    │ {product_id, │
│              │    │  name,       │
└──────────────┘    │  embedding}  │◄─── Vector Index
                    └──────────────┘
```

### 12.8 DAG（有向非巡回グラフ）可視化

`dbt docs generate` 実行時の DAG:

```
[DuckDB]                                    [Neo4j]

src:employees ─┐
               ├─► stg_employees ──┐
src:departments┘                   │
               ├─► stg_departments─┤
                                   ├─► int_employee_department ──┬──► person_node ─────────┐
                                   │                             │                         │
                                   ├─► int_employee_hierarchy ──┤──► department_node       ├─► enrich_colleagues
                                   │                             │                         │
src:products ──► stg_products ─────┤                             ├──► works_in_rel ────────┤
                                   │                             │                         │
                                   └─► int_product_embeddings ──┤──► reports_to_rel ───────┘
                                                                 │
                                                                 └──► product_node
```

---

## 13. 将来拡張（参考）

> **NOTE**: 以下は本仕様のスコープ外であるが、アーキテクチャ設計時に拡張性を確保する。

### 13.1 GraphRAG（将来）

- Knowledge Graph の自動構築
- LLM との統合による質問応答
- Vector + Graph のハイブリッド検索

### 13.2 Graph Data Science（将来）

- Neo4j GDS ライブラリとの統合
- `gds_*` マテリアライゼーション
- アルゴリズム実行結果のプロパティ書き戻し
- Graph projections の管理

---

## 14. 参考ドキュメント

- [dbt Community Adapters](https://docs.getdbt.com/docs/community-adapters)
- [dbt Adapter Contribution Guide](https://docs.getdbt.com/docs/contribute-core-adapters)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Neo4j Vector Indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [Neo4j Values and Types](https://neo4j.com/docs/cypher-manual/current/values-and-types/)
- [Neo4j Constraints](https://neo4j.com/docs/cypher-manual/current/schema/constraints/)
