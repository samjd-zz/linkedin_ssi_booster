# Product Requirements Document: Model2Vec NLP Enhancement for Knowledge Extraction and Classification

## Executive Summary

The LinkedIn SSI Booster will be enhanced with a Model2Vec-powered Text Classification MCP Server to provide fast, static embedding-based text classification capabilities. This enhancement addresses the current limitation of lacking sophisticated content categorization by automatically classifying articles, posts, and knowledge items into predefined and custom categories. The implementation will improve content curation efficiency, ensure SSI component balance, and enhance persona consistency through category-aware knowledge extraction and selection learning.

## Project Context

The LinkedIn SSI Booster is a Python automation tool that generates and schedules LinkedIn posts to improve Social Selling Index (SSI) scores across four components: establish brand, find right people, engage with insights, and build relationships. The system uses spaCy for NLP tasks, Ollama for local LLM generation, and implements a truth gate with Derivative of Truth scoring for content grounding.

Current limitations include manual review overhead in content curation and lack of category-based filtering for RSS articles. The Model2Vec enhancement will integrate seamlessly with existing spaCy NLP capabilities while adding fast classification tools that align with the project's technical stack and quality standards.

## User Stories

**As a LinkedIn professional using SSI Booster,** I want to automatically categorize curated articles by topic so that I can focus manual review on content relevant to my technical niche and SSI goals.

**As a content curator,** I want articles filtered by SSI component relevance so that generated posts maintain balanced coverage across all four SSI pillars.

**As a persona-driven content generator,** I want category-aware fact selection so that grounding uses more contextually relevant persona facts for higher credibility.

**As a learning system operator,** I want category performance tracking so that the system learns which content categories yield highest engagement for each SSI component.

**As a technical user,** I want batch classification of multiple articles so that curation cycles complete faster without compromising quality.

## Functional Requirements

### Core Classification Features

- **FR-CLASS-001**: System shall classify single text inputs with confidence scores across 10 default categories (Technology, Business, Health, Sports, Entertainment, Politics, Science, Education, Travel, Food)
- **FR-CLASS-002**: System shall support batch classification of multiple texts simultaneously for efficient processing
- **FR-CLASS-003**: System shall allow addition of custom categories with descriptive text for embedding generation
- **FR-CLASS-004**: System shall support bulk addition of multiple custom categories in single operations
- **FR-CLASS-005**: System shall provide programmatic listing of all available categories with metadata
- **FR-CLASS-006**: System shall support removal of unwanted categories from the classification system

### Content Curation Integration

- **FR-CURATE-001**: System shall automatically classify RSS articles during fetch operations
- **FR-CURATE-002**: System shall filter articles by category confidence scores above configurable threshold
- **FR-CURATE-003**: System shall map classification results to SSI components for balanced content generation
- **FR-CURATE-004**: System shall include category classifications in curation reports and dry-run output

### Knowledge Extraction Enhancement

- **FR-KNOWLEDGE-001**: System shall filter extracted facts by category relevance for improved persona grounding
- **FR-KNOWLEDGE-002**: System shall use category context to select more relevant persona facts during retrieval
- **FR-KNOWLEDGE-003**: System shall enhance truth gate validation with category-aware evidence selection

### Selection Learning Integration

- **FR-LEARN-001**: System shall incorporate category classification data into article ranking algorithms
- **FR-LEARN-002**: System shall track category performance metrics per SSI component
- **FR-LEARN-003**: System shall learn category preferences through beta-smoothed acceptance priors
- **FR-LEARN-004**: System shall include category insights in learning reports and analytics

### CLI and Configuration

- **FR-CLI-001**: System shall provide `--classify` flag to enable/disable classification during curation
- **FR-CLI-002**: System shall include category classifications in `--dot-report` output
- **FR-CLI-003**: System shall support dry-run mode showing classifications without execution
- **FR-CONFIG-001**: System shall configure Model2Vec settings through `.env` file with sensible defaults

## Non-Functional Requirements

### Performance Requirements

- **NFR-PERF-001**: Classification inference shall complete in <100ms per text on standard hardware
- **NFR-PERF-002**: Batch classification shall process 100 texts in <5 seconds
- **NFR-PERF-003**: MCP server shall maintain <5% performance overhead on curation pipeline
- **NFR-PERF-004**: Model loading shall complete in <30 seconds on first use

### Reliability Requirements

- **NFR-REL-001**: System shall achieve 95%+ classification success rate with >70% confidence scores
- **NFR-REL-002**: System shall provide graceful fallback when MCP server is unavailable
- **NFR-REL-003**: System shall handle classification failures without interrupting curation pipeline
- **NFR-REL-004**: System shall maintain existing test pass rate (>99%) with new features

### Usability Requirements

- **NFR-USAB-001**: CLI integration shall follow existing flag patterns and help documentation
- **NFR-USAB-002**: Configuration shall use existing dotenv patterns with clear environment variable names
- **NFR-USAB-003**: Error messages shall be informative and actionable for troubleshooting
- **NFR-USAB-004**: Dry-run output shall clearly display classification results for review

### Security Requirements

- **NFR-SEC-001**: MCP server shall run locally with no external API dependencies
- **NFR-SEC-002**: Model downloads shall use trusted sources (Hugging Face) with integrity verification
- **NFR-SEC-003**: No sensitive data shall be transmitted during classification operations
- **NFR-SEC-004**: Configuration shall follow existing security patterns for credential management

### Compatibility Requirements

- **NFR-COMP-001**: System shall integrate with existing Python 3.12+ environment
- **NFR-COMP-002**: MCP server shall support stdio, HTTP/SSE, and Streamable HTTP transports
- **NFR-COMP-003**: System shall maintain compatibility with existing spaCy NLP pipeline
- **NFR-COMP-004**: Dependencies shall use PEP 723 inline declarations for zero-install integration

## Project System Integration

### Content Curator Integration

- **Integration Point**: `services/content_curator/_rss_fetcher.py` - Add classification calls during article fetching
- **Integration Point**: `services/content_curator/_ssi_picker.py` - Use classification results for SSI component mapping
- **Integration Point**: `services/content_curator/curator.py` - Integrate batch classification in main curation flow
- **Data Flow**: RSS articles → Classification → Category filtering → SSI mapping → Content selection

### Avatar Intelligence Integration

- **Integration Point**: `services/avatar_intelligence/_retrieval.py` - Add category-based filtering to fact retrieval
- **Integration Point**: `services/avatar_intelligence/_confidence.py` - Include category relevance in confidence scoring
- **Integration Point**: `services/avatar_intelligence/_learning.py` - Track category performance in learning events
- **Data Flow**: Persona facts → Category filtering → Relevance scoring → Grounding selection

### Selection Learning Integration

- **Integration Point**: `services/selection_learning/_models.py` - Add category fields to CandidateRecord and PublishedRecord
- **Integration Point**: `services/selection_learning/_ranking.py` - Include category relevance in ranking algorithm
- **Integration Point**: `services/selection_learning/_priors.py` - Implement category-based acceptance priors
- **Data Flow**: Article features → Category classification → Ranking weights → Selection priors

### Truth Gate Integration

- **Integration Point**: `services/console_grounding/_truth_gate.py` - Add category validation layer
- **Integration Point**: `services/console_grounding/_retrieval.py` - Use category context for evidence selection
- **Data Flow**: Generated text → Category validation → Evidence filtering → Truth scoring

### CLI Integration

- **Integration Point**: `main.py` - Add `--classify` argument parsing and flag handling
- **Integration Point**: `services/shared.py` - Add classification configuration flags
- **Integration Point**: Reporting functions - Include category data in `--dot-report` and learning reports

## Dependencies

### Core Dependencies

- **model2vec**: `minishlab/potion-base-8M` model for static embeddings (30MB download)
- **fastmcp**: MCP server framework for Python (existing project dependency)
- **uv**: Package manager for PEP 723 dependency management

### Project Integration Dependencies

- **New Service Module**: `services/model2vec_service.py` - MCP client wrapper following existing service patterns
- **Configuration Updates**: `.env` additions for Model2Vec settings
- **Test Dependencies**: Unit tests for classification functions following existing pytest patterns

### External Dependencies

- **MCP Server**: Text Classification MCP Server (separate process, zero-install via uv)
- **Model Download**: Automatic download of `minishlab/potion-base-8M` on first use
- **Transport Layer**: MCP stdio/HTTP support (provided by fastmcp)

## Success Metrics

### Functional Metrics

- **Classification Accuracy**: 85%+ agreement with manual classification on test dataset
- **Coverage Rate**: 95%+ of articles classified with >70% confidence scores
- **SSI Balance**: <10% variance between SSI components in generated content
- **Processing Time**: <30% increase in curation pipeline execution time

### Quality Metrics

- **Test Coverage**: 90%+ test coverage for new classification functionality
- **Error Rate**: <1% classification failures in production operations
- **Fallback Success**: 100% graceful handling of MCP server unavailability
- **User Satisfaction**: >80% reduction in manual review time for categorized content

### Performance Metrics

- **Inference Speed**: <100ms average classification time per text
- **Batch Efficiency**: 10x speedup for batch vs individual classification
- **Memory Usage**: <50MB additional memory footprint
- **Startup Time**: <30 second model loading time

### Learning Metrics

- **Category Learning**: System learns category preferences within 50 published posts
- **Engagement Correlation**: 70%+ correlation between predicted and actual engagement by category
- **Prior Accuracy**: Beta-smoothed priors achieve >75% prediction accuracy for content selection

## Timeline & Milestones

### Phase 1: Core Integration (Weeks 1-2)

**Milestone 1.1**: Model2Vec service module implemented with MCP client wrapper
**Milestone 1.2**: Basic classification functions (classify_text, batch_classify) operational
**Milestone 1.3**: Configuration integration and unit tests completed
**Milestone 1.4**: MCP server integration tested across all transport modes

### Phase 2: Content Curation Enhancement (Weeks 3-4)

**Milestone 2.1**: RSS fetcher integration with article classification
**Milestone 2.2**: SSI picker updated with category-to-component mapping
**Milestone 2.3**: CLI `--classify` flag implemented and tested
**Milestone 2.4**: Category filtering logic validated with test data

### Phase 3: Learning and Reporting (Weeks 5-6)

**Milestone 3.1**: Selection learning enhanced with category features
**Milestone 3.2**: Category insights added to learning reports
**Milestone 3.3**: Confidence scoring updated for category-aware routing
**Milestone 3.4**: Truth gate integration with category validation

### Phase 4: Advanced Features & Optimization (Weeks 7-8)

**Milestone 4.1**: Custom category management tools implemented
**Milestone 4.2**: Category-based persona retrieval operational
**Milestone 4.3**: Performance analytics and batch optimization completed
**Milestone 4.4**: End-to-end integration testing and documentation finalized

### Phase 5: Production Deployment & Monitoring (Week 9)

**Milestone 5.1**: Production deployment with monitoring and alerting
**Milestone 5.2**: Performance baseline established and optimization completed
**Milestone 5.3**: User acceptance testing and feedback collection
**Milestone 5.4**: Feature documentation and training materials completed
