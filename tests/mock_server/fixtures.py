"""
Submission fixtures generator for Ulwazi SpeedGrader testing.
Generates genuine PDFs (via PyMuPDF), HTML worksheet entries, and Websnappr PNG snapshots (via PIL).
"""

import io
from typing import Any, Dict, Optional
import fitz  # PyMuPDF
from PIL import Image, ImageDraw


def create_exp05_pdf(
    student_name: str = "Sbongokuhle Mbizane",
    student_id: int = 156944,
    group: str = "Fri2",
    include_intro: bool = True,
    include_objective: bool = True,
    include_brass: bool = True,
    include_ss: bool = True,
    include_alpha: bool = True,
    include_discussion: bool = True,
    include_conclusion: bool = True,
    include_q1: bool = True,
    include_q2: bool = True,
    include_q3: bool = True,
    q2_accuracy_mode: str = "memo_14",  # "memo_14" or "standard_6"
    omit_units: bool = False,
    extra_sig_figs: bool = False,
    custom_text: Optional[str] = None,
) -> bytes:
    """Generates a realistic Experiment 05 Thermal Expansion laboratory report PDF."""
    doc = fitz.open()
    page = doc.new_page()

    u_cm = "" if omit_units else " cm"
    u_c = "" if omit_units else " °C"
    u_inv_c = "" if omit_units else " °C^-1"
    err_fmt = "0.014234" if extra_sig_figs else "0.05"

    content = []
    content.append("PHYS1000 - Laboratory Report")
    content.append("Experiment 05: Thermal Expansion of a Solid")
    content.append(f"Student: {student_name} | ID: {student_id} | Group: {group}")
    content.append("=" * 60)

    if include_intro:
        content.append("\n1. Introduction")
        content.append(
            "Thermal expansion describes the fractional change in dimensions of a material with temperature. "
            "For linear expansion of a rod of initial length l0, the change in length Delta l is proportional to "
            "the temperature rise Delta T: Delta l = alpha * l0 * Delta T, where alpha is the coefficient of linear expansion."
        )

    if include_objective:
        content.append("\n2. Principal Objectives")
        content.append(
            "The principal objectives of this experiment are to determine the linear expansion coefficients "
            "alpha of brass and stainless steel rods using an optical lever system, and to perform rigorous error analysis."
        )

    if include_brass:
        content.append("\n3. Results & Measurements: Brass")
        content.append(f"Scale deflection (d): 6.1 +/- {err_fmt}{u_cm}")
        content.append(f"Lever arm (a): 2.1 +/- {err_fmt}{u_cm}")
        content.append(f"Distance to scale (D): 100.0 +/- {err_fmt}{u_cm}")
        content.append(f"Initial length (l0): 51.0 +/- {err_fmt}{u_cm}")
        content.append(f"Initial temperature (T1): 16.0 +/- 0.5{u_c}")
        content.append(f"Final temperature (T2): 88.0 +/- 0.5{u_c}")
        content.append(f"Temperature difference (Delta T): 72.0 +/- 0.5{u_c}")

    if include_ss:
        content.append("\n4. Results & Measurements: Stainless Steel")
        content.append(f"Scale deflection (d): 5.1 +/- {err_fmt}{u_cm}")
        content.append(f"Lever arm (a): 2.1 +/- {err_fmt}{u_cm}")
        content.append(f"Distance to scale (D): 100.0 +/- {err_fmt}{u_cm}")
        content.append(f"Initial length (l0): 51.0 +/- {err_fmt}{u_cm}")
        content.append(f"Initial temperature (T1): 18.0 +/- 0.5{u_c}")
        content.append(f"Final temperature (T2): 90.0 +/- 0.5{u_c}")
        content.append(f"Temperature difference (Delta T): 72.0 +/- 0.5{u_c}")

    if include_alpha:
        content.append("\n5. Linear Expansion Calculations")
        content.append(
            "Change in length formula: Delta l = (a * d) / (2 * D)\n"
            "Linear expansion formula: alpha = Delta l / (l0 * Delta T) = (a * d) / (2 * D * l0 * Delta T)\n"
            "Uncertainty propagation: Delta alpha / alpha = Delta a / a + Delta d / d + Delta D / D + Delta l0 / l0 + Delta(Delta T) / Delta T\n"
            f"Brass: Delta l = 0.0641{u_cm}, alpha_brass = (17.44 +/- 0.71) x 10^-6{u_inv_c}\n"
            f"Stainless Steel: Delta l = 0.0536{u_cm}, alpha_ss = (14.60 +/- 0.62) x 10^-6{u_inv_c}"
        )

    # Add pages with proper textbox wrapping
    full_text = "\n".join(content)
    page.insert_textbox(fitz.Rect(40, 40, 560, 800), full_text, fontsize=9.0)

    page2 = doc.new_page()
    content2 = []

    if include_discussion:
        content2.append("\n6. Discussion")
        content2.append(
            "The experimental data demonstrates direct proportionality between thermal expansion and temperature difference. "
            "Minor discrepancies from ideal behavior may arise from thermal heat loss to the ambient environment along the steam jacket, "
            "as well as reading uncertainties in the optical lever scale."
        )

    if include_conclusion:
        content2.append("\n7. Conclusion")
        content2.append(
            f"The experimental coefficient of linear expansion for brass was determined to be (17.44 +/- 0.71) x 10^-6{u_inv_c}, "
            f"and for stainless steel (14.60 +/- 0.62) x 10^-6{u_inv_c}. These values show excellent agreement with the accepted "
            "literature values from Kaye & Laby (Brass: 17.5 x 10^-6, Stainless Steel: 14.7 x 10^-6) within experimental uncertainty."
        )

    if include_q1:
        content2.append("\n8. Question 1 (Optical Lever Derivation)")
        content2.append(
            "When the rod expands by Delta l, the optical lever of leg length a tilts by angle theta = Delta l / a. "
            "By the laws of reflection, the reflected light ray rotates by twice the mirror angle: 2*theta. "
            "Using the small-angle approximation tan(2*theta) approx 2*theta = d / D. "
            "Substituting theta = Delta l / a gives 2*(Delta l / a) = d / D, hence Delta l = (a * d) / (2 * D)."
        )

    if include_q2:
        content2.append("\n9. Question 2 (Accuracy Calculation)")
        if q2_accuracy_mode == "memo_14":
            content2.append(
                "Following the memo formulation: For 10% accuracy in alpha, relative error = 90% => Delta alpha / alpha = 0.90. "
                "Subtracting known fractional errors (Delta a/a = 0.024, Delta D/D = 0.0005, Delta l0/l0 = 0.001, Delta(Delta T)/Delta T = 0.014), "
                "we obtain Delta d / d = 0.86, which yields an accuracy of d = 14%."
            )
        else:
            content2.append(
                "Using standard error budget convention: For 10% fractional uncertainty in alpha (Delta alpha / alpha = 0.10): "
                "Delta d / d = 0.10 - (0.024 + 0.0005 + 0.001 + 0.014) = 0.0605 approx 6.1% required accuracy."
            )

    if include_q3:
        content2.append("\n10. Question 3 (Bimetallic Strip)")
        content2.append(
            "Since brass has a higher coefficient of linear expansion (17.5 x 10^-6) than stainless steel (14.7 x 10^-6), "
            "the brass layer expands more when heated. Consequently, the bimetallic strip bends towards the stainless steel side."
        )

    if custom_text:
        content2.append(f"\n{custom_text}")

    page2.insert_textbox(fitz.Rect(40, 40, 560, 800), "\n".join(content2), fontsize=9.0)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_exp06_pdf(
    student_name: str = "Sbongokuhle Mbizane",
    student_id: int = 156944,
    group: str = "Fri2",
    include_intro: bool = True,
    include_aims: bool = True,
    include_method1: bool = True,
    include_method2_table: bool = True,
    include_method2_plot: bool = True,
    include_method3: bool = True,
    include_discussion: bool = True,
    include_conclusion: bool = True,
    include_questions: bool = True,
    method2_num_rows: int = 6,
    omit_worst_fit_lines: bool = False,
    signed_magnification: bool = False,
    custom_text: Optional[str] = None,
) -> bytes:
    """Generates a realistic Experiment 06 Thin Spherical Lenses laboratory report PDF."""
    doc = fitz.open()
    page = doc.new_page()

    content = [
        "PHYS1000 - Laboratory Report",
        "Experiment 06: Thin Spherical Lenses",
        f"Student: {student_name} | ID: {student_id} | Group: {group}",
        "=" * 60,
    ]

    if include_intro:
        content.append("\n1. Introduction")
        content.append(
            "A thin converging spherical lens refracts incident parallel light rays towards a common focal point. "
            "The thin-lens equation relates object distance u, image distance v, and focal length f: 1/f = 1/u + 1/v."
        )

    if include_aims:
        content.append("\n2. Aims & Objectives")
        content.append(
            "To measure the focal length f of a thin convex converging lens using three distinct experimental methods "
            "(Distant object estimate, object-image separation, and magnification) and evaluate their comparative accuracy."
        )

    if include_method1:
        content.append("\n3. Method 1: Rough Focal Length Estimate")
        content.append(
            "Principle: For an object at great distance, u >> v, such that 1/u -> 0 and 1/f approx 1/v => f approx v. "
            "Measured image distance for distant building: v = 11.5 +/- 0.05 cm. Estimated focal length f = 11.5 cm."
        )

    if include_method2_table:
        content.append("\n4. Method 2: Object-Image Separation Data")
        content.append("Formula: d = |u2 - u1|, Delta d = Delta u1 + Delta u2, d^2/s, Delta(d^2/s) = (d^2/s)[2*(Delta d/d) + Delta s/s]")
        rows = [
            (50.0, 20.0, 30.0, 10.0, 2.00),
            (53.0, 18.4, 34.6, 16.2, 4.95),
            (56.0, 17.4, 38.6, 21.2, 8.03),
            (59.0, 16.8, 42.2, 25.4, 10.90),
            (62.0, 16.3, 45.7, 29.4, 13.90),
            (65.0, 15.9, 49.1, 33.2, 17.00),
        ][:method2_num_rows]
        for s, u1, u2, d, d2_s in rows:
            content.append(f"s={s:.1f}+/-0.05 cm | u1={u1:.1f} cm | u2={u2:.1f} cm | d={d:.1f}+/-0.1 cm | d^2/s={d2_s:.2f} cm")

    if include_method2_plot:
        content.append("\n5. Method 2: Linearization & Plot Analysis")
        wfl_note = "Lines of worst fit omitted." if omit_worst_fit_lines else "Includes centroid, best-fit line, and 2 lines of worst fit."
        content.append(
            f"Linearization: d^2 / s = 1.0 * s - 4f. The graph of d^2/s vs s has theoretical slope = 1 and intercept = -4f. "
            f"From the plot (y-intercept c = -48.0 +/- 0.8 cm): f = -c / 4 = 12.0 +/- 0.1 cm. {wfl_note}"
        )

    page.insert_textbox(fitz.Rect(40, 40, 560, 800), "\n".join(content), fontsize=9.0)

    page2 = doc.new_page()
    content2 = []

    if include_method3:
        content2.append("\n6. Method 3: Magnification Data & Statistics")
        content2.append("Formula: m = -v/u, f = v / (|m| + 1)")
        mag_sign = -1.0 if signed_magnification else 1.0
        m3_rows = [
            (15.0, 58.9, 3.93 * mag_sign, 11.9),
            (18.0, 36.3, 2.02 * mag_sign, 12.0),
            (21.0, 27.5, 1.31 * mag_sign, 11.9),
            (24.0, 24.2, 1.01 * mag_sign, 12.0),
            (27.0, 21.0, 0.78 * mag_sign, 11.8),
            (30.0, 20.2, 0.67 * mag_sign, 12.1),
        ]
        for u, v, m, f in m3_rows:
            content2.append(f"u={u:.1f} cm | v={v:.1f} cm | m={m:+.2f} | f={f:.1f} cm")
        content2.append("Statistical Analysis: Mean focal length f_bar = 12.0 cm, Sample standard deviation sigma = 0.014 cm.")
        content2.append("Reported Focal Length: f = 12.0 +/- 0.014 cm.")

    if include_discussion:
        content2.append("\n7. Discussion")
        content2.append(
            "Comparing the three methods: Method 1 provides a rapid preliminary estimate (11.5 cm) with coarse precision. "
            "Method 2 eliminates lens thickness errors and yields 12.0 +/- 0.1 cm via graphical linearization. "
            "Method 3 yields the highest statistical precision at 12.0 +/- 0.014 cm. All methods show consistent agreement."
        )

    if include_conclusion:
        content2.append("\n8. Conclusion")
        content2.append(
            "The focal length of the thin converging spherical lens was determined to be 12.0 +/- 0.1 cm across methods, "
            "confirming theoretical thin lens optics and optical separation principles."
        )

    if include_questions:
        content2.append("\n9. Questions")
        content2.append(
            "Question 1: The minus sign in m = -v/u indicates that the image formed is inverted relative to the object.\n"
            "Question 2: From the lens equation 1/f = 1/u + 1/v, as u -> infinity, 1/u -> 0, so 1/f = 1/v => v = f.\n"
            "Question 3: (i) Focal point is the point where rays parallel to the principal axis converge. "
            "(ii) Focal length is the distance from the optical center of the lens to its principal focal point."
        )

    if custom_text:
        content2.append(f"\n{custom_text}")

    page2.insert_textbox(fitz.Rect(40, 40, 560, 800), "\n".join(content2), fontsize=9.0)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_lab3_part_a_html(
    box1: str = "The ball moves along a straight line at constant velocity upwards and to the right.",
    box2: str = "r_f = r_i + v*t",
    box3: str = "33 +/- 0.5 mm",
    box4: str = "-p_x",
    box5: str = "The system is closed because no matter or mass is exchanged with the surroundings. It is not isolated because an external normal force acts during the wall collision.",
    box6: str = "-p_x * i + p_y * j",
    box7: str = "p_x * i - p_y * j",
) -> str:
    """Generates standard HTML text submission for Lab 3 Part A (Boxes 1-7)."""
    return f"""
<div class="user_content">
    <h3>Computer Lab 3: Worksheet Part A</h3>
    <p><b>Box 1:</b> {box1}</p>
    <p><b>Box 2:</b> {box2}</p>
    <p><b>Box 3:</b> {box3}</p>
    <p><b>Box 4:</b> {box4}</p>
    <p><b>Box 5:</b> {box5}</p>
    <p><b>Box 6:</b> {box6}</p>
    <p><b>Box 7:</b> {box7}</p>
</div>
""".strip()


def create_lab3_part_b_html(
    box8: str = "The ball is stationary because no virtual simulation time has elapsed yet.",
    box9: str = "Valid when velocity is constant (zero acceleration, net external force is zero).",
    box10: str = "Yes, agrees mathematically. The code statement is an incremental state assignment in memory.",
    box11: str = "The ball appears stationary because only a single tiny time step dt was executed.",
    box12: str = "The ball moves northeast continuously and passes right through the wall.",
    box13: str = "Expected the ball to bounce elastically off the wall and reverse direction.",
    box14: str = "The velocity should be -v_x in the horizontal axis and unchanged in vertical.",
    box15: str = "The ball moves towards the right wall, collides, reverses direction, and travels left.",
    box16: str = "a) Ball moves upwards while bouncing back and forth between left and right walls. b) Normal force acts horizontally (Newton's 3rd Law).",
    box17: str = "The ball reflects continuously off all four walls inside the 2D bounding enclosure.",
) -> str:
    """Generates standard HTML text submission for Lab 3 Part B (Boxes 8-17)."""
    return f"""
<div class="user_content">
    <h3>Computer Lab 3: Worksheet Part B</h3>
    <p><b>Box 8:</b> {box8}</p>
    <p><b>Box 9:</b> {box9}</p>
    <p><b>Box 10:</b> {box10}</p>
    <p><b>Box 11:</b> {box11}</p>
    <p><b>Box 12:</b> {box12}</p>
    <p><b>Box 13:</b> {box13}</p>
    <p><b>Box 14:</b> {box14}</p>
    <p><b>Box 15:</b> {box15}</p>
    <p><b>Box 16:</b> {box16}</p>
    <p><b>Box 17:</b> {box17}</p>
</div>
""".strip()


REFERENCE_VPYTHON_CODE = """from vpython import *

scene = canvas(title="Ball in a Box", width=600, height=400)
box_size = 10.0
deltat = 0.01

wall_right = box(pos=vector(box_size, 0, 0), size=vector(0.2, 2*box_size, 0.2), color=color.red)
wall_left = box(pos=vector(-box_size, 0, 0), size=vector(0.2, 2*box_size, 0.2), color=color.red)
wall_top = box(pos=vector(0, box_size, 0), size=vector(2*box_size, 0.2, 0.2), color=color.blue)
wall_bottom = box(pos=vector(0, -box_size, 0), size=vector(2*box_size, 0.2, 0.2), color=color.blue)

ball = sphere(pos=vector(0, 0, 0), radius=0.5, color=color.yellow, make_trail=True)
ball.velocity = vector(5.0, 3.0, 0)

while True:
    rate(100)
    ball.pos = ball.pos + ball.velocity * deltat
    
    if ball.pos.x + ball.radius >= wall_right.pos.x:
        ball.velocity.x = -abs(ball.velocity.x)
    elif ball.pos.x - ball.radius <= wall_left.pos.x:
        ball.velocity.x = abs(ball.velocity.x)
        
    if ball.pos.y + ball.radius >= wall_top.pos.y:
        ball.velocity.y = -abs(ball.velocity.y)
    elif ball.pos.y - ball.radius <= wall_bottom.pos.y:
        ball.velocity.y = abs(ball.velocity.y)
"""


def create_websnappr_png(
    code_text: str = REFERENCE_VPYTHON_CODE,
    width: int = 2560,
    height: int = 2184,
) -> bytes:
    """Generates a high-resolution Websnappr PNG screenshot of the Trinket/VPython code."""
    img = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (width, 80)], fill=(45, 45, 48))
    draw.text((40, 25), "Trinket / GlowScript IDE - Computer Lab 3 Final Code", fill=(220, 220, 220))

    # Render code lines
    y = 120
    for i, line in enumerate(code_text.splitlines(), start=1):
        # Line number
        draw.text((40, y), f"{i:3d} |", fill=(100, 100, 100))
        # Code content
        draw.text((120, y), line, fill=(240, 240, 240))
        y += 40
        if y > height - 100:
            break

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
