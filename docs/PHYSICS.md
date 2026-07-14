# Physics notes (MuSlice)

## Model

Transmission of a monochromatic X-ray beam through a slab:

\[
T = \frac{I}{I_0} = \exp(-\mu\, t_{\mathrm{eff}})
\]

with linear attenuation coefficient

\[
\mu = \left(\frac{\mu}{\rho}\right)_{\mathrm{mix}} \rho,\quad
\left(\frac{\mu}{\rho}\right)_{\mathrm{mix}} = \sum_i w_i \left(\frac{\mu}{\rho}\right)_i
\]

where \(w_i\) are **mass fractions**. Elemental \((\mu/\rho)\) values are taken from **xraydb** (Elam by default; Chantler optional).

If the sample is tilted by incidence angle \(\alpha\) from normal:

\[
t_{\mathrm{eff}} = t / \cos\alpha
\]

## Multi-layer stack

Along the beam path:

\[
T_{\mathrm{total}} = \prod_i \exp(-\mu_i t_i) = \exp\Bigl(-\sum_i \mu_i t_i\Bigr)
\]

Windows (Kapton, Be, quartz), air gaps, and the sample can be budgeted together.

## Design targets

- **Target \(T\)**: solve for sample thickness \(t = -\ln T / \mu_{\mathrm{eff}}\) (sample-only), or subtract other layers’ \(\sum\mu t\) first when “total stack” is selected.
- **Target \(\mu t\)**: \(t = (\mu t)/\mu_{\mathrm{eff}}\).
- Common practical window: \(\mu t \approx 0.5\text{–}1.2\) (\(T \approx 0.61\text{–}0.30\)).

## What this is not

- Not a full Monte-Carlo transport code.
- Density **estimate** is only a rough mixture model; measured \(\rho\) is required for absolute thickness.
- Exposure estimator scales from a reference shot; it is not an absolute photon-statistics calculator.
- Detector Q coverage uses a simple orthogonal-plane geometry.
