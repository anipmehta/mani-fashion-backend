# Requirements Document

## Introduction

This document defines the requirements for MANI, a direct-to-consumer custom fashion platform whose core product is a deterministic pattern engine built on Parsons-method drafting formulas. MANI closes the full loop from customer body measurements through mathematically generated slopers, tailor production, finished garment delivery, and structured fit feedback. Unlike B2B tools such as FashionINSTA.AI (which serve professional pattern makers), MANI targets end consumers who never see a pattern — they interact with their garment visually while the platform handles the math behind the scenes.

The platform is built in three strategic phases. Phase 1 (POC) validates the core loop: measurements → pattern engine → tailor → garment → fit feedback. Phase 2 adds the visual design console and scaling infrastructure. Phase 3 layers intelligence (ML-based fit prediction), advanced visualization, third-party integrations, and beta testing at scale. This document captures requirements across all three phases, clearly labeled by phase.

## Glossary

- **MANI**: The direct-to-consumer custom fashion platform that enables customers to get tailored garments through a deterministic pattern engine and tailor partner network.
- **Pattern_Engine**: The core computational component that implements Parsons-method drafting formulas to generate production-ready slopers from customer measurements. Supports three base blocks: bodice/top, trouser/bottom, and sleeve.
- **Sloper**: A base pattern block (also called a block pattern) that represents a precise, fitted template for a garment type. Slopers are generated mathematically from body measurements and serve as the foundation for all design modifications.
- **Base_Block**: One of three foundational sloper types supported by the Pattern_Engine: bodice/top block, trouser/bottom block, and sleeve block.
- **Customer**: An end consumer who provides body measurements and orders custom-fitted garments through MANI.
- **Measurement_Profile**: A structured set of body measurements provided by a Customer, containing at minimum: chest, waist, hip, shoulder width, arm length, inseam, and torso length.
- **Design_Console**: The visual interface (Phase 2) where Customers manipulate garment design elements (neckline, hem, sleeve length, silhouette) while the Pattern_Engine recalculates the underlying sloper in real-time.
- **Constrained_Modification**: A design change within the Design_Console that has been validated not to break the mathematical integrity of the underlying sloper.
- **Tailor_Partner**: A vetted tailoring workshop (initially the partner workshop in India) that produces garments from MANI-generated slopers.
- **Partner_Portal**: The interface (Phase 2) through which Tailor_Partners receive slopers, manage production workflow, and communicate status.
- **Fit_Feedback**: Structured data captured after a Customer receives a garment, recording what fit well, what did not, and by how much (in measurable units).
- **Fit_Feedback_System**: The subsystem that collects, stores, and organizes Fit_Feedback data to validate sloper accuracy and inform future improvements.
- **Order_Manager**: The subsystem responsible for tracking garment orders from measurement submission through production to delivery.
- **Fit_Predictor**: The ML/rules-based engine (Phase 3) that uses accumulated Fit_Feedback data to predict and improve fit outcomes.
- **Body_Scanner**: A third-party body measurement service (e.g., 3DLook, TrueToForm) offered as a premium alternative to manual measurement input (Phase 2).

## Requirements

---

### Phase 1 — Pattern Engine Foundation (POC)

---

### Requirement 1: Manual Measurement Input

**User Story:** As a Customer, I want to enter my body measurements manually, so that MANI can generate a sloper tailored to my body.

#### Acceptance Criteria

1. THE MANI platform SHALL present a measurement input form that collects at minimum: chest, waist, hip, shoulder width, arm length, inseam, and torso length.
2. WHEN a Customer submits measurements, THE MANI platform SHALL validate that all required fields are present and contain numeric values within anatomically plausible ranges.
3. IF a Customer submits a measurement value outside the plausible range, THEN THE MANI platform SHALL display a specific error message identifying the out-of-range field and the acceptable range.
4. WHEN all measurements pass validation, THE MANI platform SHALL store the measurements as a Measurement_Profile associated with the Customer's account.
5. WHEN a Customer updates their Measurement_Profile, THE MANI platform SHALL retain the previous Measurement_Profile as history.

### Requirement 2: Parsons-Based Sloper Generation

**User Story:** As a Customer, I want MANI to generate a production-ready sloper from my measurements, so that a tailor can produce a garment that fits my body precisely.

#### Acceptance Criteria

1. WHEN a valid Measurement_Profile is provided, THE Pattern_Engine SHALL generate a sloper for each requested Base_Block type (bodice/top, trouser/bottom, or sleeve) using deterministic Parsons-method drafting formulas.
2. THE Pattern_Engine SHALL output slopers in DXF format for digital pattern cutting and PDF format for manual tailor use.
3. WHEN a sloper is generated, THE Pattern_Engine SHALL validate that all pattern pieces are geometrically closed, contain no overlapping seam lines, and include seam allowance markings.
4. FOR ALL valid Measurement_Profiles, generating a sloper and then extracting the measurements back from the sloper geometry SHALL produce values equivalent to the original Measurement_Profile within a tolerance of 2mm (round-trip property).
5. WHEN two Measurement_Profiles differ by a single measurement value, THE Pattern_Engine SHALL produce slopers that differ only in the pattern regions affected by that measurement (metamorphic property).
6. THE Pattern_Engine SHALL include grain line indicators, notch marks, and piece labels on every generated sloper.

### Requirement 3: Sloper Output and Export

**User Story:** As a founder, I want slopers exported in standard formats, so that the Tailor_Partner can use them directly in production.

#### Acceptance Criteria

1. THE Pattern_Engine SHALL export each sloper as a multi-page PDF containing: a full-scale pattern layout, a measurement reference table, and assembly instructions.
2. THE Pattern_Engine SHALL export each sloper as a DXF file compatible with standard CAD/CAM cutting systems.
3. WHEN a sloper is exported to PDF, THE Pattern_Engine SHALL render pattern pieces at 1:1 scale with alignment marks for tiled printing.
4. WHEN a sloper is exported to DXF, THE Pattern_Engine SHALL encode each pattern piece as a separate layer with labeled seam lines, cut lines, and notch points.
5. FOR ALL valid slopers, exporting to DXF and then parsing the DXF file back into internal sloper representation SHALL produce an equivalent sloper (round-trip property).

### Requirement 4: Tailor Partner Sloper Delivery

**User Story:** As a founder, I want to send generated slopers to the Tailor_Partner in India, so that garments can be produced from the patterns.

#### Acceptance Criteria

1. WHEN a Customer confirms an order, THE MANI platform SHALL transmit the sloper files (DXF and PDF) and the associated Measurement_Profile to the assigned Tailor_Partner via email or secure file transfer.
2. THE MANI platform SHALL include with each sloper delivery: the Customer's order identifier, the Base_Block type, fabric specifications (if selected), and any special instructions.
3. WHEN the Tailor_Partner confirms receipt of the sloper, THE Order_Manager SHALL update the order status to "received by tailor."
4. IF the Tailor_Partner reports that a sloper is unclear or cannot be produced, THEN THE MANI platform SHALL flag the order for founder review with the Tailor_Partner's feedback attached.

### Requirement 5: Order Tracking (POC)

**User Story:** As a Customer, I want to track my order status, so that I know when to expect my garment.

#### Acceptance Criteria

1. WHEN a Customer submits an order, THE Order_Manager SHALL assign a unique order identifier and display it to the Customer.
2. THE Order_Manager SHALL track and display the following order statuses: measurement submitted, sloper generated, sent to tailor, received by tailor, in production, shipped, and delivered.
3. WHEN the order status changes, THE Order_Manager SHALL notify the Customer via email.
4. THE Order_Manager SHALL display the current status and order history on the Customer's account page.

### Requirement 6: Structured Fit Feedback Collection

**User Story:** As a founder, I want to capture structured fit feedback after each garment is delivered, so that I can validate sloper accuracy and improve the Pattern_Engine over time.

#### Acceptance Criteria

1. WHEN a Customer's order status changes to "delivered," THE Fit_Feedback_System SHALL prompt the Customer to submit Fit_Feedback within 7 days.
2. THE Fit_Feedback_System SHALL collect feedback for each body region relevant to the Base_Block type (e.g., chest, waist, hip for a bodice/top) with the following fields: fit rating (too tight, slightly tight, perfect, slightly loose, too loose) and numeric adjustment value in centimeters.
3. THE Fit_Feedback_System SHALL allow the Customer to add free-text comments for each body region.
4. WHEN Fit_Feedback is submitted, THE Fit_Feedback_System SHALL associate the feedback with the original Measurement_Profile and the generated sloper.
5. THE Fit_Feedback_System SHALL store all Fit_Feedback records for use in future Pattern_Engine validation and improvement.
6. THE Fit_Feedback_System SHALL display a summary of all past Fit_Feedback records on the Customer's account page.

---

### Phase 2 — Design Console + Scaling

---

### Requirement 7: Visual Design Console

**User Story:** As a Customer, I want to manipulate garment design elements visually, so that I can customize my garment without needing to understand pattern making.

#### Acceptance Criteria

1. THE Design_Console SHALL present the Customer with visual controls for modifying: neckline shape, hem length, sleeve length, silhouette (fitted, regular, relaxed), and pocket placement.
2. WHEN the Customer changes any design element, THE Design_Console SHALL display the updated garment visualization within 2 seconds.
3. WHEN the Customer changes any design element, THE Pattern_Engine SHALL recalculate the underlying sloper to reflect the modification in real-time.
4. THE Design_Console SHALL allow the Customer to save and name multiple design drafts associated with their account.
5. WHEN the Customer finalizes a design, THE Design_Console SHALL generate a design specification summary listing all selected options and the corresponding sloper parameters.

### Requirement 8: Constrained Modification System

**User Story:** As a founder, I want the Design_Console to only allow modifications that are mathematically valid, so that customers cannot create designs that break the pattern.

#### Acceptance Criteria

1. THE Design_Console SHALL enforce Constrained_Modifications by validating each design change against the Pattern_Engine's mathematical rules before applying the change.
2. IF a Customer attempts a modification that would violate the sloper's structural integrity, THEN THE Design_Console SHALL prevent the change and display a message explaining why the modification is not available.
3. THE Design_Console SHALL visually indicate which design elements are modifiable for the current garment state and which are locked.
4. WHEN a Constrained_Modification is applied, THE Pattern_Engine SHALL verify that the resulting sloper remains geometrically valid (all pieces closed, no overlapping seam lines, seam allowances intact).

### Requirement 9: Body Scanning Integration

**User Story:** As a Customer, I want the option to use a body scanning service instead of manual input, so that I can get more accurate measurements with less effort.

#### Acceptance Criteria

1. THE MANI platform SHALL offer body scanning via a third-party service (3DLook or TrueToForm) as a premium measurement option alongside manual input.
2. WHEN a Customer initiates a body scan, THE Body_Scanner SHALL guide the Customer through the scanning process and return a structured Measurement_Profile.
3. IF the Body_Scanner fails to capture a valid scan, THEN THE MANI platform SHALL display a clear error message and allow the Customer to retry or fall back to manual measurement input.
4. WHEN a scan-derived Measurement_Profile is received, THE MANI platform SHALL store it identically to a manually entered Measurement_Profile so that the Pattern_Engine processes both types uniformly.

### Requirement 10: Partner Portal for Tailor Workflow

**User Story:** As a Tailor_Partner, I want a dedicated portal to receive slopers, manage production, and communicate status, so that I can efficiently produce garments at scale.

#### Acceptance Criteria

1. THE Partner_Portal SHALL allow the Tailor_Partner to view all assigned orders with sloper files, Measurement_Profiles, and design specifications.
2. THE Partner_Portal SHALL allow the Tailor_Partner to update production status (received, in-progress, quality-check, shipped) for each order.
3. WHEN the Tailor_Partner updates the production status, THE Order_Manager SHALL reflect the updated status to the Customer within 60 seconds.
4. THE Partner_Portal SHALL allow the Tailor_Partner to submit clarifying questions or issue reports for specific orders.
5. THE Partner_Portal SHALL record the Tailor_Partner's quoted production cost for each order.

### Requirement 11: Order Tracking (Full)

**User Story:** As a Customer, I want detailed order tracking with estimated delivery dates, so that I can plan around my garment's arrival.

#### Acceptance Criteria

1. THE Order_Manager SHALL display an estimated delivery date based on the Tailor_Partner's production timeline and shipping estimates.
2. WHEN the Tailor_Partner updates the shipping status, THE Order_Manager SHALL provide tracking information (carrier and tracking number) to the Customer.
3. THE Order_Manager SHALL notify the Customer via email at each major status transition: sloper sent, production started, shipped, and delivered.

---

### Phase 3 — Intelligence + Polish

---

### Requirement 12: Fit Prediction Engine

**User Story:** As a founder, I want the platform to predict fit outcomes using accumulated feedback data, so that sloper accuracy improves over time without manual formula tuning.

#### Acceptance Criteria

1. WHEN sufficient Fit_Feedback data has been collected (minimum 50 feedback records per Base_Block type), THE Fit_Predictor SHALL generate adjustment recommendations for the Pattern_Engine's sloper formulas.
2. THE Fit_Predictor SHALL identify systematic fit issues (e.g., "bodice/top slopers are consistently 1cm tight at the chest for Customers with chest measurements above 100cm") from aggregated Fit_Feedback data.
3. WHEN a new Measurement_Profile is submitted, THE Fit_Predictor SHALL flag any measurements that historically correlate with fit issues and suggest preemptive adjustments.
4. THE Fit_Predictor SHALL provide a confidence score (0-100) for each adjustment recommendation based on the volume and consistency of supporting Fit_Feedback data.

### Requirement 13: Style Recommendations

**User Story:** As a Customer, I want style recommendations based on my body type, so that I can discover designs that are likely to fit and flatter me.

#### Acceptance Criteria

1. WHEN a Customer has a stored Measurement_Profile, THE MANI platform SHALL suggest Base_Block types and design modifications that complement the Customer's body proportions.
2. THE MANI platform SHALL base style recommendations on aggregated Fit_Feedback data from Customers with similar Measurement_Profiles.
3. WHEN a Customer views a style recommendation, THE MANI platform SHALL display the recommendation rationale (e.g., "Customers with similar proportions rated this neckline highly for fit and comfort").

### Requirement 14: Advanced 3D Visualization

**User Story:** As a Customer, I want to see a realistic 3D preview of my garment on a body model matching my measurements, so that I can evaluate the design before ordering.

#### Acceptance Criteria

1. WHEN the Customer makes a design change in the Design_Console, THE MANI platform SHALL render an updated 3D visualization of the garment on a body model scaled to the Customer's Measurement_Profile.
2. WHEN the Customer rotates or zooms the 3D preview, THE MANI platform SHALL respond within 500 milliseconds.
3. IF the 3D visualization engine encounters a rendering error, THEN THE MANI platform SHALL display a fallback 2D garment illustration and notify the Customer that the 3D preview is temporarily unavailable.

### Requirement 15: Third-Party E-Commerce Integration

**User Story:** As a founder, I want MANI's design experience to be embeddable in Shopify and Wix stores, so that I can reach customers through existing retail channels.

#### Acceptance Criteria

1. THE MANI platform SHALL provide an embeddable widget that renders the Design_Console within a Shopify storefront.
2. THE MANI platform SHALL provide an embeddable widget that renders the Design_Console within a Wix storefront.
3. WHEN a Customer completes a design in the embedded Design_Console, THE MANI platform SHALL pass the order details to the host platform's checkout flow.
4. THE MANI platform SHALL authenticate with the host platform using standard API keys or OAuth tokens.

### Requirement 16: Beta Testing Program

**User Story:** As a founder, I want to recruit and manage beta testers who provide structured feedback, so that I can iterate on the platform before general launch.

#### Acceptance Criteria

1. THE MANI platform SHALL provide a beta tester signup form that collects: name, email, clothing preferences, body type, and willingness to provide feedback.
2. WHEN a beta tester completes an order, THE MANI platform SHALL prompt the beta tester to submit feedback covering: ease of use, design accuracy, fit satisfaction, and overall experience.
3. THE MANI platform SHALL aggregate beta tester feedback into a dashboard showing satisfaction scores and common themes.
4. THE MANI platform SHALL support a target of at least 50 beta testers for the initial testing phase.

### Requirement 17: Sustainability Tracking

**User Story:** As a Customer, I want to see sustainability and ethical sourcing information for my garment, so that I can trust that my purchase is produced responsibly.

#### Acceptance Criteria

1. THE MANI platform SHALL display sustainability information for each fabric option including: material origin, certifications (e.g., GOTS, OEKO-TEX), and environmental impact rating.
2. THE MANI platform SHALL display ethical sourcing information for each Tailor_Partner including: fair labor certification status and working conditions summary.
3. WHEN a Customer views a garment summary, THE MANI platform SHALL include a sustainability score based on the selected materials and production partner.
