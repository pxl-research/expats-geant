"""Unit tests for core domain models."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from m_shared.models import (
    AnswerOption,
    Citation,
    Question,
    QuestionType,
    Response,
    Section,
    Session,
    Survey,
)


class TestAnswerOption:
    """Test AnswerOption model."""
    
    def test_create_answer_option(self):
        """Test creating a valid answer option."""
        option = AnswerOption(id="opt_1", text="Strongly Agree", value=5)
        assert option.id == "opt_1"
        assert option.text == "Strongly Agree"
        assert option.value == 5
    
    def test_answer_option_with_metadata(self):
        """Test answer option with metadata."""
        option = AnswerOption(
            id="opt_1",
            text="Yes",
            value=1,
            metadata={"color": "green", "icon": "check"}
        )
        assert option.metadata["color"] == "green"
        assert option.metadata["icon"] == "check"
    
    def test_answer_option_serialization(self):
        """Test JSON serialization."""
        option = AnswerOption(id="opt_1", text="Maybe")
        json_data = option.model_dump()
        assert json_data["id"] == "opt_1"
        assert json_data["text"] == "Maybe"
        
        # Test deserialization
        reconstructed = AnswerOption(**json_data)
        assert reconstructed.id == option.id


class TestQuestion:
    """Test Question model."""
    
    def test_create_multiple_choice_question(self):
        """Test creating a multiple choice question."""
        q = Question(
            id="q1",
            text="Select all that apply",
            type=QuestionType.MULTIPLE_CHOICE,
            answer_options=[
                AnswerOption(id="opt_1", text="Option A"),
                AnswerOption(id="opt_2", text="Option B"),
            ]
        )
        assert q.type == QuestionType.MULTIPLE_CHOICE
        assert len(q.answer_options) == 2
    
    def test_create_single_choice_question(self):
        """Test creating a single choice question (Likert scale)."""
        q = Question(
            id="q2",
            text="How satisfied are you?",
            type=QuestionType.SINGLE_CHOICE,
            answer_options=[
                AnswerOption(id="opt_1", text="Very satisfied", value=5),
                AnswerOption(id="opt_2", text="Satisfied", value=4),
                AnswerOption(id="opt_3", text="Neutral", value=3),
            ]
        )
        assert q.type == QuestionType.SINGLE_CHOICE
        assert len(q.answer_options) == 3
    
    def test_create_open_ended_question(self):
        """Test creating an open-ended question."""
        q = Question(
            id="q3",
            text="Please explain your answer",
            type=QuestionType.OPEN_ENDED
        )
        assert q.type == QuestionType.OPEN_ENDED
        assert len(q.answer_options) == 0
    
    def test_create_ranking_question(self):
        """Test creating a ranking question."""
        q = Question(
            id="q4",
            text="Rank these priorities",
            type=QuestionType.RANKING,
            answer_options=[
                AnswerOption(id="opt_1", text="Cost"),
                AnswerOption(id="opt_2", text="Quality"),
                AnswerOption(id="opt_3", text="Speed"),
            ]
        )
        assert q.type == QuestionType.RANKING
        assert len(q.answer_options) == 3
    
    def test_create_slider_question(self):
        """Test creating a slider question."""
        q = Question(
            id="q5",
            text="Rate your experience (0-100)",
            type=QuestionType.SLIDER,
            min_value=0,
            max_value=100,
            step=1
        )
        assert q.type == QuestionType.SLIDER
        assert q.min_value == 0
        assert q.max_value == 100
        assert q.step == 1
    
    def test_choice_question_requires_options(self):
        """Test that choice questions require answer options."""
        with pytest.raises(ValidationError) as exc_info:
            Question(
                id="q_bad",
                text="Choose one",
                type=QuestionType.SINGLE_CHOICE,
                answer_options=[]  # Invalid: no options
            )
        assert "requires at least one answer option" in str(exc_info.value)
    
    def test_slider_question_requires_min_max(self):
        """Test that slider questions require min/max values."""
        with pytest.raises(ValidationError) as exc_info:
            Question(
                id="q_bad",
                text="Rate something",
                type=QuestionType.SLIDER
                # Missing min_value and max_value
            )
        assert "must have min_value and max_value" in str(exc_info.value)


class TestSection:
    """Test Section model."""
    
    def test_create_section(self):
        """Test creating a section with questions."""
        section = Section(
            id="sec_1",
            title="Demographics",
            description="Tell us about yourself",
            questions=[
                Question(id="q1", text="What is your age?", type=QuestionType.OPEN_ENDED)
            ],
            order=1
        )
        assert section.id == "sec_1"
        assert section.title == "Demographics"
        assert len(section.questions) == 1
        assert section.order == 1
    
    def test_section_serialization(self):
        """Test section JSON serialization."""
        section = Section(
            id="sec_1",
            title="Section One",
            questions=[]
        )
        json_data = section.model_dump()
        reconstructed = Section(**json_data)
        assert reconstructed.id == section.id


class TestSurvey:
    """Test Survey model."""
    
    def test_create_survey(self):
        """Test creating a survey with sections."""
        survey = Survey(
            id="survey_1",
            title="Employee Satisfaction Survey",
            description="Annual feedback survey",
            sections=[
                Section(id="sec_1", title="Demographics", questions=[]),
                Section(id="sec_2", title="Satisfaction", questions=[])
            ],
            metadata={"version": "1.0", "author": "HR"}
        )
        assert survey.id == "survey_1"
        assert survey.title == "Employee Satisfaction Survey"
        assert len(survey.sections) == 2
        assert survey.metadata["version"] == "1.0"
    
    def test_survey_serialization(self):
        """Test survey JSON serialization."""
        survey = Survey(
            id="survey_1",
            title="Test Survey",
            sections=[]
        )
        json_data = survey.model_dump()
        reconstructed = Survey(**json_data)
        assert reconstructed.id == survey.id


class TestResponse:
    """Test Response model."""
    
    def test_create_response(self):
        """Test creating a response."""
        response = Response(
            id="resp_1",
            question_id="q1",
            answer_value="Very satisfied",
            session_id="sess_123"
        )
        assert response.id == "resp_1"
        assert response.question_id == "q1"
        assert response.answer_value == "Very satisfied"
        assert response.session_id == "sess_123"
        assert isinstance(response.timestamp, datetime)
    
    def test_response_with_list_answer(self):
        """Test response with multiple choice answer."""
        response = Response(
            id="resp_2",
            question_id="q2",
            answer_value=["opt_1", "opt_3", "opt_5"]
        )
        assert isinstance(response.answer_value, list)
        assert len(response.answer_value) == 3
    
    def test_response_with_numeric_answer(self):
        """Test response with numeric answer."""
        response = Response(
            id="resp_3",
            question_id="q3",
            answer_value=75
        )
        assert response.answer_value == 75


class TestCitation:
    """Test Citation model."""
    
    def test_create_citation(self):
        """Test creating a citation."""
        citation = Citation(
            id="cite_1",
            source_id="doc_abc",
            chunk_id="chunk_5",
            position_start=120,
            position_end=450,
            position_percentage=0.15,
            highlights=["relevant excerpt"]
        )
        assert citation.id == "cite_1"
        assert citation.source_id == "doc_abc"
        assert citation.chunk_id == "chunk_5"
        assert citation.position_start == 120
        assert citation.position_end == 450
        assert citation.position_percentage == 0.15
        assert len(citation.highlights) == 1
    
    def test_citation_with_metadata(self):
        """Test citation with metadata."""
        citation = Citation(
            id="cite_2",
            source_id="doc_xyz",
            chunk_id="chunk_10",
            metadata={"relevance_score": 0.92, "context": "financial report"}
        )
        assert citation.metadata["relevance_score"] == 0.92


class TestSession:
    """Test Session model."""
    
    def test_create_session(self):
        """Test creating a session."""
        session = Session(
            session_id="sess_abc123",
            user_id="user_456",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        assert session.session_id == "sess_abc123"
        assert session.user_id == "user_456"
        assert session.isolation_scope == "user"
        assert not session.is_expired()
    
    def test_session_expiration(self):
        """Test session expiration logic."""
        # Create expired session
        session = Session(
            session_id="sess_expired",
            user_id="user_789",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        assert session.is_expired()
    
    def test_session_time_remaining(self):
        """Test calculating time remaining."""
        session = Session(
            session_id="sess_active",
            user_id="user_101",
            expires_at=datetime.utcnow() + timedelta(hours=12)
        )
        remaining = session.time_remaining()
        assert remaining.total_seconds() > 0
        assert remaining.total_seconds() < 13 * 3600  # Less than 13 hours
    
    def test_session_auto_expiration(self):
        """Test automatic expiration calculation from TTL."""
        session = Session(
            session_id="sess_auto",
            user_id="user_202",
            expires_at=None,  # Should auto-calculate
            metadata={"ttl_hours": 48}
        )
        # Should be set to ~48 hours from now
        time_diff = (session.expires_at - session.created_at).total_seconds()
        assert abs(time_diff - (48 * 3600)) < 10  # Within 10 seconds


class TestModelIntegration:
    """Test model interactions and integration."""
    
    def test_complete_survey_structure(self):
        """Test building a complete survey with all components."""
        survey = Survey(
            id="survey_full",
            title="Complete Survey Example",
            description="Demonstrating all model relationships",
            sections=[
                Section(
                    id="sec_1",
                    title="Satisfaction",
                    questions=[
                        Question(
                            id="q1",
                            text="How satisfied are you?",
                            type=QuestionType.SINGLE_CHOICE,
                            answer_options=[
                                AnswerOption(id="opt_1", text="Very satisfied", value=5),
                                AnswerOption(id="opt_2", text="Satisfied", value=4),
                            ]
                        ),
                        Question(
                            id="q2",
                            text="Any comments?",
                            type=QuestionType.OPEN_ENDED
                        )
                    ]
                )
            ]
        )
        
        # Verify structure
        assert len(survey.sections) == 1
        assert len(survey.sections[0].questions) == 2
        assert survey.sections[0].questions[0].type == QuestionType.SINGLE_CHOICE
        assert survey.sections[0].questions[1].type == QuestionType.OPEN_ENDED
        
        # Test serialization
        json_data = survey.model_dump()
        reconstructed = Survey(**json_data)
        assert reconstructed.id == survey.id
        assert len(reconstructed.sections) == len(survey.sections)
