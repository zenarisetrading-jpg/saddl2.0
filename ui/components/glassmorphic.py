"""
Glassmorphic UI Components for SADDL AdPulse
=============================================

Reusable glassmorphic-styled components for consistent UI.

Usage:
    from ui.components.glassmorphic import (
        glassmorphic_card,
        progress_indicator,
        value_prop_card,
        info_banner
    )

    # Render in Streamlit
    st.markdown(glassmorphic_card("<p>Content</p>"), unsafe_allow_html=True)
"""

import textwrap
from config.design_system import COLORS, TYPOGRAPHY, SPACING, GLASSMORPHIC
from ui.components.icons import glassmorphic_icon


def glassmorphic_card(content: str, padding: str = None) -> str:
    """
    Create a glassmorphic card container.

    Args:
        content: HTML content to place inside the card
        padding: CSS padding value (defaults to SPACING['lg'])

    Returns:
        HTML string for the card
    """
    if padding is None:
        padding = SPACING['lg']

    return textwrap.dedent(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {padding};
            box-shadow: {GLASSMORPHIC['box_shadow']};
        ">
            {content}
        </div>
    ''').strip()


def progress_indicator(current_step: int, total_steps: int) -> str:
    """
    Create a glassmorphic progress bar with step indicator.

    Args:
        current_step: Current step number (1-indexed)
        total_steps: Total number of steps

    Returns:
        HTML string for the progress indicator
    """
    progress_percent = (current_step / total_steps) * 100

    # Build step dots
    dots_html = ""
    for i in range(1, total_steps + 1):
        if i < current_step:
            # Completed
            dot_style = f"background: {COLORS['primary']}; border-color: {COLORS['primary']};"
        elif i == current_step:
            # Current
            dot_style = f"background: {COLORS['primary']}; border-color: {COLORS['primary']}; box-shadow: 0 0 12px {COLORS['primary']};"
        else:
            # Upcoming
            dot_style = f"background: transparent; border-color: {COLORS['text_muted']};"

        dots_html += f'''
            <div style="
                width: 12px;
                height: 12px;
                border-radius: 50%;
                border: 2px solid;
                {dot_style}
                transition: all 0.3s ease;
            "></div>
        '''

    return textwrap.dedent(f'''
        <div style="margin: {SPACING['lg']} 0 {SPACING['xl']} 0;">
            <!-- Progress bar -->
            <div style="
                width: 100%;
                height: 4px;
                background: {GLASSMORPHIC['background']};
                border-radius: 2px;
                overflow: hidden;
                margin-bottom: {SPACING['md']};
            ">
                <div style="
                    width: {progress_percent}%;
                    height: 100%;
                    background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['primary_light']});
                    transition: width 0.5s ease;
                    box-shadow: 0 0 12px {COLORS['primary']};
                "></div>
            </div>

            <!-- Step dots -->
            <div style="
                display: flex;
                justify-content: center;
                gap: {SPACING['md']};
                align-items: center;
            ">
                {dots_html}
            </div>

            <!-- Step text -->
            <div style="
                text-align: center;
                color: {COLORS['text_muted']};
                font-size: {TYPOGRAPHY['body_sm']};
                margin-top: {SPACING['sm']};
            ">
                Step {current_step} of {total_steps}
            </div>
        </div>
    ''').strip()


def value_prop_card(icon_name: str, title: str, description: str) -> str:
    """
    Create a value proposition card with icon.

    Args:
        icon_name: Name of the glassmorphic icon
        title: Card title
        description: Card description text

    Returns:
        HTML string for the value prop card
    """
    icon_svg = glassmorphic_icon(icon_name, size=56)

    return textwrap.dedent(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {SPACING['xl']};
            text-align: center;
            transition: all 0.3s ease;
            height: 100%;
            cursor: default;
            margin-bottom: {SPACING['md']};
        " onmouseover="
            this.style.transform='translateY(-4px)';
            this.style.borderColor='rgba(37, 99, 235, 0.3)';
            this.style.boxShadow='0 12px 40px rgba(0, 0, 0, 0.4)';
        " onmouseout="
            this.style.transform='translateY(0)';
            this.style.borderColor='rgba(255, 255, 255, 0.1)';
            this.style.boxShadow='none';
        ">
            <div style="margin-bottom: {SPACING['md']};">
                {icon_svg}
            </div>
            <h3 style="
                color: {COLORS['text_primary']};
                font-size: {TYPOGRAPHY['heading_sm']};
                font-weight: 600;
                margin: 0 0 {SPACING['sm']} 0;
            ">
                {title}
            </h3>
            <p style="
                color: {COLORS['text_secondary']};
                font-size: {TYPOGRAPHY['body_md']};
                line-height: 1.6;
                margin: 0;
            ">
                {description}
            </p>
        </div>
    ''').strip()


def info_banner(message: str, banner_type: str = 'info') -> str:
    """
    Create a styled information banner.

    Args:
        message: Banner message (can include HTML)
        banner_type: Type of banner ('info', 'success', 'warning', 'error')

    Returns:
        HTML string for the banner
    """
    colors = {
        'info': COLORS['info'],
        'success': COLORS['success'],
        'warning': COLORS['warning'],
        'error': COLORS['error'],
    }
    color = colors.get(banner_type, colors['info'])

    return textwrap.dedent(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: {SPACING['md']} {SPACING['lg']};
            margin: {SPACING['md']} 0;
            color: {COLORS['text_primary']};
            font-size: {TYPOGRAPHY['body_md']};
        ">
            {message}
        </div>
    ''').strip()


def feature_card(icon_name: str, title: str, description: str, features: list) -> str:
    """
    Create a feature overview card with bullet points.

    Args:
        icon_name: Name of the glassmorphic icon
        title: Feature title
        description: Feature description
        features: List of feature bullet points

    Returns:
        HTML string for the feature card
    """
    icon_svg = glassmorphic_icon(icon_name, size=48)

    features_html = ""
    for feature in features:
        features_html += f'''
            <li style="
                color: {COLORS['text_secondary']};
                margin-bottom: 8px;
                display: flex;
                align-items: flex-start;
                gap: 8px;
            ">
                <span style="color: {COLORS['success']}; font-size: 14px;">&#10003;</span>
                <span>{feature}</span>
            </li>
        '''

    return textwrap.dedent(f'''
        <div style="
            background: {GLASSMORPHIC['background']};
            backdrop-filter: {GLASSMORPHIC['backdrop_filter']};
            border: {GLASSMORPHIC['border']};
            border-radius: {GLASSMORPHIC['border_radius']};
            padding: {SPACING['xl']};
            height: 100%;
        ">
            <div style="display: flex; align-items: center; gap: {SPACING['md']}; margin-bottom: {SPACING['md']};">
                {icon_svg}
                <h3 style="
                    color: {COLORS['text_primary']};
                    font-size: {TYPOGRAPHY['heading_sm']};
                    font-weight: 600;
                    margin: 0;
                ">
                    {title}
                </h3>
            </div>
            <p style="
                color: {COLORS['text_secondary']};
                font-size: {TYPOGRAPHY['body_md']};
                line-height: 1.6;
                margin-bottom: {SPACING['md']};
            ">
                {description}
            </p>
            <ul style="
                list-style: none;
                padding: 0;
                margin: 0;
                font-size: {TYPOGRAPHY['body_sm']};
            ">
                {features_html}
            </ul>
        </div>
    ''').strip()


def checklist_item(text: str, completed: bool = False, current: bool = False) -> str:
    """
    Create a checklist item for onboarding progress.

    Args:
        text: Item text
        completed: Whether the item is completed
        current: Whether this is the current item

    Returns:
        HTML string for the checklist item
    """
    if completed:
        icon = f'<span style="color: {COLORS["success"]}; font-size: 20px;">&#10003;</span>'
        text_style = f"color: {COLORS['text_secondary']}; text-decoration: line-through;"
    elif current:
        icon = f'<span style="color: {COLORS["primary"]}; font-size: 20px;">&#9679;</span>'
        text_style = f"color: {COLORS['text_primary']}; font-weight: 500;"
    else:
        icon = f'<span style="color: {COLORS["text_muted"]}; font-size: 20px;">&#9675;</span>'
        text_style = f"color: {COLORS['text_muted']};"

    return textwrap.dedent(f'''
        <div style="
            display: flex;
            align-items: center;
            gap: {SPACING['md']};
            padding: {SPACING['sm']} 0;
        ">
            {icon}
            <span style="{text_style} font-size: {TYPOGRAPHY['body_md']};">
                {text}
            </span>
        </div>
    ''').strip()
